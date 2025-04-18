# FastAPI User Authentication API

A FastAPI-based user authentication API with JWT token support.

## Features

- User registration and login
- JWT token authentication
- OTP verification
- User profile management

## Project Structure

```
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── render.yaml         # Render configuration
├── Procfile           # Process file for deployment
├── .env.example       # Example environment variables
└── README.md          # Project documentation
```

## Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file from `.env.example` and update the values
5. Run the application:
   ```bash
   python main.py
   ```

## Render Deployment

### Prerequisites
- GitHub account
- Render account
- PostgreSQL database (will be provisioned by Render)

### Deployment Steps

1. **Prepare Your Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   ```

2. **Create GitHub Repository**
   - Go to GitHub
   - Create a new repository
   - Push your code:
     ```bash
     git remote add origin <your-github-repo-url>
     git push -u origin main
     ```

3. **Deploy on Render**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click "New +" and select "Web Service"
   - Connect your GitHub repository
   - Configure the service:
     - Name: michelanglo-api
     - Environment: Python
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Add PostgreSQL database:
     - Click "New +" and select "PostgreSQL"
     - Name: michelanglo-db
     - Plan: Free
   - Add Environment Variables:
     - `SECRET_KEY`: Generate a secure random string
     - `ALGORITHM`: HS256
     - `FLASK_ENV`: production
     - `CORS_ORIGINS`: Your production domain
   - Click "Create Web Service"

### Verify Deployment

1. Check deployment status in Render dashboard
2. Test the API endpoints using the provided Render URL:
   ```bash
   # Register
   curl -X POST "https://your-render-url.onrender.com/register" -d "name=test&email=test@example.com&password=123456"

   # Login
   curl -X POST "https://your-render-url.onrender.com/login" -d "email=test@example.com&password=123456"
   ```

## API Endpoints

- `POST /register` - Register a new user
- `POST /login` - User login
- `GET /user` - Get user details
- `POST /send-otp` - Send OTP
- `POST /verify-otp` - Verify OTP

## Environment Variables

See `.env.example` for required environment variables.

## Troubleshooting

1. **Build Fails**
   - Check Render logs
   - Verify requirements.txt
   - Clear build cache in Render

2. **Database Connection Issues**
   - Verify DATABASE_URL in Render
   - Check PostgreSQL service status
   - Review application logs

3. **Application Crashes**
   - Check application logs
   - Verify environment variables
   - Ensure all dependencies are in requirements.txt

## License

MIT 