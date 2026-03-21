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
python app.py
```

Then open:

```text
http://127.0.0.1:8000
```

## Deploy on Render

This app is now set up to run on Render:

- It listens on `0.0.0.0`
- It uses Render's `PORT` environment variable automatically
- A `render.yaml` file is included for service setup
- A `requirements.txt` file is included, even though there are no third-party packages

If you deploy manually on Render, the important start command is:

```bash
python app.py
```

## Notes

- No database
- No local storage
- No third-party dependencies
- Player names and skill ratings are hardcoded in `app.py` for now
