# Movie Chatbot

A FastAPI-based movie chatbot that scrapes IMDb data and provides movie information through a web interface.

## Features

- Scrapes movie data from IMDb using Selenium
- Stores movie information in MongoDB
- Provides a chat interface for movie queries
- Admin dashboard for managing movies
- Real-time movie updates using scheduler

## Setup

1. Install Docker and Docker Compose
2. Clone the repository
3. Build and run the services:
   ```bash
   docker-compose up --build
   ```

4. Access the application at http://localhost:8000

## Project Structure

```
movie_chatbot/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── database.py          # Database setup
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic models
│   ├── scraper.py           # IMDB scraping logic
│   ├── auth.py              # Authentication logic
│   ├── crud.py              # Database operations
│   ├── utils.py             # Utility functions
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css    # CSS files
│   │   └── js/
│   │       └── script.js    # JavaScript files
│   └── templates/
│       ├── base.html        # Base template
│       ├── index.html       # Main page
│       ├── admin.html       # Admin dashboard
│       └── login.html      # Admin login
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker configuration
├── docker-compose.yml       # Docker compose for services
└── README.md
```
