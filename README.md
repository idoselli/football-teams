# Football Team Splitter

A lightweight Python web app for choosing who is coming to a football game and generating 3 balanced team combinations.

## What it does

- Lets you choose from 20 fictional players
- Supports selecting between 12 and 15 players
- Splits the selected group into 3 teams as evenly as possible
- Returns 3 different balanced suggestions with minimal repeated team groupings
- Works well on phones and desktop browsers

## Run it

Use any normal Python 3 installation:

```bash
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:8000
```

## Deploy on Vercel

This app is now set up to run on Vercel as a Flask app:

- `app.py` exposes a Flask `app`
- `api/index.py` is the Vercel Python entrypoint
- `vercel.json` routes requests to the Flask app
- Static files are served from `/static`

To deploy:

```bash
vercel
```

## Notes

- No database
- No local storage
- Player names and skill ratings are loaded from `ratings.csv`
