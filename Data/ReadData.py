import pandas as pd

# Read JSON file into DataFrame
df = pd.read_json('AllBlocks.txt', lines=True,chunksize=1)

# Process DataFrame as needed

for chunk in df:
  print(chunk.head())
  break