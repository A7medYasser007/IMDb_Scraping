import pandas as pd
import numpy as np
import re
from collections import Counter, defaultdict
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from scipy.sparse import hstack
import matplotlib.pyplot as plt
import networkx as nx
import seaborn as sns
import ast
import squarify
from itertools import combinations
from mpl_toolkits.mplot3d import Axes3D
from wordcloud import WordCloud
from pandas.plotting import parallel_coordinates

# Load data
df = pd.read_csv("C:\\Users\\ahmed\\Desktop\\imdb\\movies_with_imdb_data.csv")

# 1. Fill numeric missing values with mean
numeric_cols = ['rating', 'votes', 'runtime']
df[numeric_cols] = df[numeric_cols].apply(lambda col: col.fillna(col.mean()))
df['year'] = df['year'].dropna()

# 2. Drop rows with missing string values
string_cols = ['genres', 'directors', 'cast', 'plot', 'countries', 'languages']
df = df.dropna(subset=string_cols)
for col in string_cols:
    df = df[df[col].str.strip() != '']

# 3. Convert comma-separated string values to lists
multi_feature_cols = ['genres', 'directors', 'cast', 'countries', 'languages']
for col in multi_feature_cols:
    # Handle both string representations and actual lists
    df[col] = df[col].apply(lambda x: 
        [item.strip(" '\"") for item in str(x).strip("[]").split(',')] 
        if isinstance(x, str) else x)

# 4. Standardize age_group values using regex
# Ensure uppercased first
df['age_group'] = df['age_group'].str.upper().str.strip()

# Apply replacements
df['age_group'] = df['age_group'].str.replace(r'\+?18', 'NC-17', regex=True)
df['age_group'] = df['age_group'].str.replace(r'NC/?17', 'NC-17', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bM(/PG)?\b', 'PG', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bGP\b', 'PG', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bPG[- ]?13\b', 'PG-13', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bPG\b', 'PG', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bNOT RATED\b|\bUNRATED\b', 'UNRATED', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bPASSED\b|\bAPPROVED\b', 'G', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bTV[\s-]?G\b', 'TV-G', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bTV[\s-]?PG\b', 'TV-PG', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bTV[\s-]?14\b', 'TV-14', regex=True)
df['age_group'] = df['age_group'].str.replace(r'\bTV[\s-]?MA\b', 'TV-MA', regex=True)

# Final cleanup: strip extra spaces
df['age_group'] = df['age_group'].str.strip()

# 5. Format runtime from minutes to HH:MM:SS
df['runtime'] = pd.to_timedelta(df['runtime'], unit='m').astype(str).str.extract(r'(\d+:\d+:\d+)')[0]

# 6. Format votes into K or M
def format_votes(v):
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    elif v >= 1_000:
        return f"{v/1_000:.0f}K"
    return str(int(v))
df['votes_numeric'] = df['votes']
df['votes'] = df['votes'].apply(format_votes)

# 7. Clean special characters from plot text
df['plot'] = df['plot'].apply(lambda x: re.sub(r'[^a-zA-Z0-9\s]', '', str(x)))

# Convert runtime to minutes for analysis
def time_to_minutes(t):
    try:
        h, m, s = map(int, str(t).split(":"))
        return h * 60 + m + s / 60
    except:
        return None
df['runtime_minutes'] = df['runtime'].apply(time_to_minutes)

# Get top 1000 movies based on rating and votes
top_movies = df.sort_values(by=['rating', 'votes_numeric'], ascending=False).head(1000)

# Flatten list-type columns
def flatten_list_column(column):
    return [item for sublist in column for item in sublist]

# Analysis results
top_actors = Counter(flatten_list_column(top_movies['cast'])).most_common(10)
top_directors = Counter(flatten_list_column(top_movies['directors'])).most_common(10)

genre_counts = Counter(flatten_list_column(top_movies['genres']))
total_genres = sum(genre_counts.values())
genre_percentages = {genre: f"{(count/total_genres)*100:.1f}%" 
                    for genre, count in genre_counts.items()}
genre_percentages = dict(sorted(genre_percentages.items(), 
                             key=lambda x: float(x[1][:-1]), reverse=True))

top_countries = Counter(flatten_list_column(top_movies['countries'])).most_common(10)
top_languages = Counter(flatten_list_column(top_movies['languages'])).most_common(10)

def top_avg_rating(df, col):
    items = []
    for entry in set(flatten_list_column(df[col])):
        subset = df[df[col].apply(lambda x: entry in x)]
        avg_rating = subset['rating'].mean()
        items.append((entry, avg_rating))
    return sorted(items, key=lambda x: x[1], reverse=True)[:5]

top_directors_by_rating = top_avg_rating(top_movies, 'directors')
top_actors_by_rating = top_avg_rating(top_movies, 'cast')
correlation = df[['runtime_minutes', 'rating']].corr().iloc[0, 1]

# Machine Learning Preparation
df = df.dropna(subset=['age_group', 'plot', 'genres'])
df['age_group'] = df['age_group'].astype('category')

# TF-IDF Vectorizer for plot text
tfidf = TfidfVectorizer(max_features=1000, stop_words='english')
plot_features = tfidf.fit_transform(df['plot'])

# MultiLabelBinarizer for genres
mlb = MultiLabelBinarizer()
genres_encoded = mlb.fit_transform(df['genres'])

# Combine features and split data
X = hstack([plot_features, genres_encoded])
y = df['age_group'].cat.codes
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train Random Forest Classifier
clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train, y_train)

# Predict and evaluate
y_pred = clf.predict(X_test)
used_labels = sorted(np.unique(y_test))
used_names = df['age_group'].cat.categories[used_labels]

print("\n🔹 Classification Report:")
print(classification_report(y_test, y_pred, target_names=used_names))

# Save cleaned dataset
df.to_csv("C:\\Users\\ahmed\\Desktop\\imdb\\cleaned_movies_data.csv", index=False)

# Print analysis results
print("🔸 Top 10 Actors:")
print(top_actors)
print("\n🔸 Top 10 Directors:")
print(top_directors)
print("\n🔸 Genre Percentages:")
print(genre_percentages)
print("\n🔸 Top Countries:")
print(top_countries)
print("\n🔸 Top Languages:")
print(top_languages)
print("\n🔸 Top Directors by Average Rating:")
print(top_directors_by_rating)
print("\n🔸 Top Actors by Average Rating:")
print(top_actors_by_rating)
print(f"\n🔸 Correlation between Runtime and Rating: {correlation:.3f}")

# Visualization 1: Genre Frequency
plt.figure(figsize=(10,6))
all_genres = df.explode('genres')
genre_counts = all_genres['genres'].value_counts()
sns.barplot(x=genre_counts.values, y=genre_counts.index, palette="viridis")
plt.title("Genre Frequency")
plt.xlabel("Count")
plt.ylabel("Genre")
plt.tight_layout()
plt.show()

# Visualization 2: Rating Distribution
plt.figure(figsize=(8,5))
sns.histplot(df['rating'], bins=20, kde=True, color='blue')
plt.title("Rating Distribution")
plt.xlabel("Rating")
plt.ylabel("Frequency")
plt.tight_layout()
plt.show()

# Visualization 3: Votes vs Rating
plt.figure(figsize=(8,5))
sns.regplot(data=df, x='votes_numeric', y='rating', scatter_kws={'alpha':0.5}, line_kws={'color': 'red'})
plt.title("Votes vs. Rating")
plt.xlabel("Votes")
plt.ylabel("Rating")
plt.tight_layout()
plt.show()

# Visualization 4: Top Directors
plt.figure(figsize=(10,6))
top_directors = df.explode('directors')['directors'].value_counts().head(10)
sns.barplot(x=top_directors.values, y=top_directors.index, palette="mako")
plt.title("Top 10 Directors by Number of Movies")
plt.xlabel("Number of Movies")
plt.ylabel("Director")
plt.tight_layout()
plt.show()

# Visualization 5: Runtime Distribution
plt.figure(figsize=(8,5))
sns.boxplot(data=df, x='runtime_minutes', color='lightgreen')
plt.title("Runtime Distribution")
plt.xlabel("Runtime (minutes)")
plt.tight_layout()
plt.show()

# Visualization 6: Country Treemap
country_counts = df['countries'].apply(lambda x: x[0] if len(x) > 0 else '').value_counts().head(15)
plt.figure(figsize=(14, 10))  
squarify.plot(
    sizes=country_counts.values, 
    label=country_counts.index, 
    alpha=0.8,
    text_kwargs={'fontsize': 10, 'wrap': True}
)
plt.title('Movie Count by First Country (Top 15 Countries)')
plt.axis('off')
plt.show()

# Visualization 7: Word Cloud
text = " ".join(df['plot'].dropna().tolist())
wordcloud = WordCloud(width=1000, height=500, background_color='white').generate(text)
plt.figure(figsize=(15,7))
plt.imshow(wordcloud, interpolation='bilinear')
plt.axis('off')
plt.title("Word Cloud from Plot Descriptions")
plt.tight_layout()
plt.show()

# Visualization 8: Rating by Decade
df['decade'] = (df['year'] // 10) * 10
decade_avg = df.groupby('decade')['rating'].mean().reset_index()
plt.figure(figsize=(10,5))
sns.lineplot(data=decade_avg, x='decade', y='rating', marker='o')
plt.title("Average Rating by Decade")
plt.xlabel("Decade")
plt.ylabel("Average Rating")
plt.grid(True)
plt.tight_layout()
plt.show()

# Visualization 9: Actor Co-occurrence Heatmap
df_top10 = df.head(10).copy()
co_occurrence = defaultdict(int)
for cast_list in df_top10['cast']:
    top_actors = cast_list[:3]
    for pair in combinations(top_actors, 2):
        sorted_pair = tuple(sorted(pair))  
        co_occurrence[sorted_pair] += 1

all_actors = sorted(set([actor for pair in co_occurrence for actor in pair]))
matrix = pd.DataFrame(0, index=all_actors, columns=all_actors)
for (actor1, actor2), count in co_occurrence.items():
    matrix.loc[actor1, actor2] = count
    matrix.loc[actor2, actor1] = count 

plt.figure(figsize=(18, 15))
sns.heatmap(matrix, cmap="YlGnBu", linewidths=0.5, linecolor='gray', square=True)
plt.title("Actor Co-occurrence Heatmap (Top 3 Actors in Top 10 Movies)", fontsize=16)
plt.xticks(rotation=90)
plt.yticks(rotation=0)
plt.tight_layout()
plt.show()

# Visualization 10: 3D Scatter Plot
fig = plt.figure(figsize=(10,7))
ax = fig.add_subplot(111, projection='3d')
ax.scatter(df['rating'], df['runtime_minutes'], df['votes_numeric'], c='teal', alpha=0.5)
ax.set_xlabel('Rating')
ax.set_ylabel('Runtime (min)')
ax.set_zlabel('Votes')
ax.set_title('3D Scatter Plot: Rating × Runtime × Votes')
plt.tight_layout()
plt.show()

# Visualization 11: Parallel Coordinates
sample = df[['rating', 'runtime_minutes', 'votes_numeric', 'age_group']].dropna().sample(500)
plt.figure(figsize=(12,6))
parallel_coordinates(sample, class_column='age_group', colormap=plt.get_cmap("Set1"))
plt.title("Parallel Coordinates Plot")
plt.tight_layout()
plt.show()

# Visualization 12: Actor-Director Network
df_top50 = df.head(50).copy()
G = nx.Graph()
for _, row in df_top50.iterrows():
    for director in row['directors']:
        for actor in row['cast'][:3]:
            G.add_node(director, type='director')
            G.add_node(actor, type='actor')
            G.add_edge(director, actor)

node_colors = ['#1f77b4' if data['type'] == 'director' else '#ff7f0e' for _, data in G.nodes(data=True)]
plt.figure(figsize=(16, 12))
pos = nx.spring_layout(G, k=0.5, seed=42)
nx.draw(G, pos, node_color=node_colors, edge_color='gray', with_labels=True,
        node_size=700, font_size=8, font_weight='bold')
plt.title("Actor-Director Collaboration Network (Top Movies)", fontsize=14)
plt.tight_layout()
plt.show()

# Visualization 13: Genre Popularity Over Time
rows = []
for _, row in df.iterrows():
    year = row['year']
    for genre in row['genres']:
        rows.append({'year': year, 'genre': genre})

df_expanded = pd.DataFrame(rows)
genre_counts = df_expanded.groupby(['year', 'genre']).size().unstack(fill_value=0)
genre_counts = genre_counts.sort_index()

plt.figure(figsize=(14, 7))
genre_counts.plot.area(colormap='tab20', figsize=(14, 7))
plt.title('Genre Popularity Over Time', fontsize=16)
plt.xlabel('Year', fontsize=12)
plt.ylabel('Number of Movies', fontsize=12)
plt.grid(True)
plt.tight_layout()
plt.show()
