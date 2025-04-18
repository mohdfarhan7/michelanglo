from fastapi import FastAPI, Depends, HTTPException, Request, Form, Header
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional, Dict
import urllib.parse
import os
from dotenv import load_dotenv
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="User Authentication API")

# Database Models
Base = declarative_base()

class User(Base):
    __tablename__ = 'Users'
    Id = Column(Integer, primary_key=True)
    FullName = Column(String(100), nullable=False)
    Email = Column(String(255), nullable=False)
    PasswordHash = Column(String(255), nullable=False)
    DeviceId = Column(String(255), nullable=True)
    CreatedAt = Column(DateTime, server_default=func.now())
    Status = Column(Boolean, default=True)
    Mobile = Column(String(15), nullable=True)
    OTP = Column(String(6), nullable=True)
    IsPhoneVerified = Column(Boolean, default=False)

# Global variables for database connection
engine = None
SessionLocal = None

def get_db():
    if not SessionLocal:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    global engine, SessionLocal
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Get database URL from environment or use default
            db_url = os.getenv('DATABASE_URL')
            if not db_url:
                # Fallback to individual environment variables
                db_user = os.getenv('DB_USERNAME', 'postgres')
                db_pass = os.getenv('DB_PASSWORD', '')
                db_host = os.getenv('DB_HOST', 'localhost')
                db_port = os.getenv('DB_PORT', '5432')
                db_name = os.getenv('DB_NAME', 'michelanglo')
                db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            
            logger.info(f"Attempting to connect to database (attempt {attempt + 1}/{max_retries})")
            
            # Create engine with connection pooling and automatic reconnection
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30
            )
            
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Database connection successful")
            
            # Create session factory
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            
            # Create all tables
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            return
            
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("Failed to connect to database after all retries")
                raise

# Health check endpoint with database verification
@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint that verifies both application and database status.
    """
    try:
        # Test database connection
        if engine:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                db_status = "healthy"
        else:
            db_status = "not initialized"
        
        return {
            "status": "healthy",
            "database": db_status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "database": "error",
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to the API"}

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# JWT configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key_here')
ALGORITHM = os.getenv('ALGORITHM', 'HS256')

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"status": "0", "message": "Endpoint not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=500,
        content={"status": "0", "message": "Internal server error"}
    )

# Signup API
@app.post("/register")
async def signup(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    mobile: Optional[str] = Form(None),
    device_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        if not all([name, email, password]):
            return JSONResponse(
                status_code=400,
                content={"status": "0", "message": "Full name, email, and password are required."}
            )

        # Check if email already exists
        if db.query(User).filter(User.Email == email).first():
            return JSONResponse(
                status_code=409,
                content={"status": "0", "message": "Email already registered."}
            )

        # Create new user with required fields
        new_user = User(
            FullName=name,
            Email=email,
            PasswordHash=generate_password_hash(password),
            Mobile=mobile,
            DeviceId=device_id,
            Status=True,
            OTP=None,
            IsPhoneVerified=False
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return JSONResponse(
            status_code=201,
            content={
                "status": "1", 
                "message": "New User Register Successfully.",
                "user_id": new_user.Id
            }
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"status": "0", "message": f"Registration failed: {str(e)}"}
        )

# Login API
@app.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not email or not password:
        return JSONResponse(
            status_code=400,
            content={"status": "0", "message": "Email and password are required."}
        )

    user = db.query(User).filter(User.Email == email).first()
    if not user or not check_password_hash(user.PasswordHash, password):
        return JSONResponse(
            status_code=401,
            content={"status": "0", "message": "Invalid email or password."}
        )

    # Generate JWT token
    payload = {
        "iss": "Issuer of the JWT",
        "aud": "Audience that the JWT",
        "sub": "Subject of the JWT",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=30),
        "email": user.Email,
        "id": str(user.Id)
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return JSONResponse(
        status_code=200,
        content={
            "status": "1",
            "message": "Login successful",
            "result": {
                "id": str(user.Id),
                "user_name": user.FullName,
                "email": user.Email,
                "password": user.PasswordHash,
                "created_at": user.CreatedAt.strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": user.DeviceId,
                "access_token": token
            }
        }
    )

# Get User Details API
@app.get("/user")
async def get_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    if not authorization:
        return JSONResponse(
            status_code=401,
            content={"status": "0", "message": "Token is missing."}
        )

    try:
        if not authorization.startswith('Bearer '):
            return JSONResponse(
                status_code=401,
                content={"status": "0", "message": "Invalid token format. Use 'Bearer <token>'"}
            )

        token = authorization.split(' ')[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        user = db.query(User).filter(User.Id == payload['id']).first()
        if not user:
            return JSONResponse(
                status_code=404,
                content={"status": "0", "message": "User not found."}
            )

        return JSONResponse(
            status_code=200,
            content={
                "status": "1",
                "message": "User details retrieved successfully",
                "result": {
                    "id": str(user.Id),
                    "user_name": user.FullName,
                    "email": user.Email,
                    "created_at": user.CreatedAt.strftime("%Y-%m-%d %H:%M:%S"),
                    "device_id": user.DeviceId,
                    "status": 1 if user.Status else 0
                }
            }
        )

    except jwt.ExpiredSignatureError:
        return JSONResponse(
            status_code=401,
            content={"status": "0", "message": "Token has expired."}
        )
    except jwt.InvalidTokenError:
        return JSONResponse(
            status_code=401,
            content={"status": "0", "message": "Invalid token."}
        )
    except Exception as e:
        return JSONResponse(
            status_code=401,
            content={"status": "0", "message": f"Error: {str(e)}"}
        )

# Send OTP endpoint
@app.post("/send-otp")
async def send_otp(
    mobile: str = Form(...),
    db: Session = Depends(get_db)
):
    if not mobile:
        return JSONResponse(
            status_code=400,
            content={"status": "0", "message": "Mobile number is required."}
        )

    try:
        default_otp = "9999"
        user = db.query(User).filter(User.Mobile == mobile).first()
        
        if user:
            if user.IsPhoneVerified and user.Email:
                return JSONResponse(
                    status_code=400,
                    content={"status": "0", "message": "Mobile number already registered."}
                )
            user.OTP = default_otp
            db.commit()
        else:
            new_user = User(
                Mobile=mobile,
                OTP=default_otp,
                IsPhoneVerified=False
            )
            db.add(new_user)
            db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "status": "1",
                "message": "OTP sent successfully",
                "result": {
                    "mobile": mobile,
                    "otp": default_otp
                }
            }
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"status": "0", "message": f"Error sending OTP: {str(e)}"}
        )

# Verify OTP endpoint
@app.post("/verify-otp")
async def verify_otp(
    mobile: str = Form(...),
    otp: str = Form(...),
    db: Session = Depends(get_db)
):
    if not mobile or not otp:
        return JSONResponse(
            status_code=400,
            content={"status": "0", "message": "Mobile number and OTP are required."}
        )

    user = db.query(User).filter(User.Mobile == mobile).first()
    
    if not user or user.OTP != otp:
        return JSONResponse(
            status_code=400,
            content={"status": "0", "message": "Invalid mobile number or OTP"}
        )

    user.IsPhoneVerified = True
    db.commit()

    return JSONResponse(
        status_code=200,
        content={
            "status": "1",
            "message": "OTP Verified Successfully",
            "result": {
                "mobile": mobile,
                "is_verified": True
            }
        }
    )

# Register endpoint (requires verified phone)
@app.post("/register-verified")
async def register_verified(
    mobile: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    device_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if not all([mobile, name, email, password]):
        return JSONResponse(
            status_code=400,
            content={"status": "0", "message": "Mobile, name, email, and password are required."}
        )

    try:
        user = db.query(User).filter(User.Mobile == mobile).first()
        
        if not user:
            return JSONResponse(
                status_code=400,
                content={"status": "0", "message": "Please verify your phone number first."}
            )

        if not user.IsPhoneVerified:
            return JSONResponse(
                status_code=400,
                content={"status": "0", "message": "Please verify your phone number first."}
            )

        if db.query(User).filter(User.Email == email).first():
            return JSONResponse(
                status_code=400,
                content={"status": "0", "message": "Email already registered."}
            )

        user.FullName = name
        user.Email = email
        user.PasswordHash = generate_password_hash(password)
        user.DeviceId = device_id
        
        db.commit()

        payload = {
            "iss": "Issuer of the JWT",
            "aud": "Audience that the JWT",
            "sub": "Subject of the JWT",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(days=30),
            "id": str(user.Id)
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        return JSONResponse(
            status_code=200,
            content={
                "status": "1",
                "message": "User registered successfully",
                "result": {
                    "id": str(user.Id),
                    "user_name": user.FullName,
                    "email": user.Email,
                    "mobile": user.Mobile,
                    "created_at": user.CreatedAt.strftime("%Y-%m-%d %H:%M:%S"),
                    "device_id": user.DeviceId,
                    "status": "ACTIVE",
                    "access_token": token
                }
            }
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"status": "0", "message": f"Registration error: {str(e)}"}
        )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 