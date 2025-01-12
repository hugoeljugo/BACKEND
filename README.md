# WhiskrNet Backend
Welcome to the WhiskrNet backend! This FastAPI application provides the server-side logic for user authentication, post management, real-time chat, and more.

## Getting Started
1. Clone this repository or download its contents.
2. Navigate to the project directory and create a virtual environment:
```sh
python -m venv venv
```
3. Activate the virtual environment:
- on windows:
```sh
.\venv\Scripts\activate
```
- on macOS/Linux:
```sh
source venv/bin/activate
```
4. Install dependencies:
```sh
pip install -r requirements.txt
```
5. Run the development server:
```sh
fastapi dev
```
6. Open your browser at http://localhost:8000/docs to see the API documentation.

## Project Structure
Below is a brief overview of key files and directories:

- main.py: 
Main application entry point that initializes FastAPI, sets up routes, and configures middleware.

- config.py: 
Configuration settings for the application, including environment variables and constants.

- models: 
SQLModel-based ORM models representing database tables (e.g., User, Post, Chat).

- routers: 
FastAPI routers that define API endpoints for authentication, user management, posts, chat, etc.

- dependencies.py: 
Common dependencies used across the application, such as database sessions and authentication.

- services: 
Utility services for logging, caching, and other auxiliary functions.

## Features
1. Authentication & Authorization

- Email-based registration and login.
- JWT token authentication.
- Rate-limited login attempts (3/minute).
- Password hashing with bcrypt.
- Session management.

2. User Management

- Customizable user profiles.
- Profile picture upload and management.
- Email verification system.
- Follow/unfollow functionality.
- User activity tracking.

3. Posts System

- Create and edit text posts.
- Like/unlike posts (rate limit: 10/minute).
- Post creation limits (5/minute).
- View post engagement metrics.
- Post visibility controls.

4. Media Management

- Image upload support.
- Supported formats: JPG, JPEG, PNG, WebP.
- Automatic image optimization.
- Maximum file size: 10MB.
- Secure file storage.

5. Real-Time Features

- WebSocket-based chat system.
- Online status indicators.
- Real-time post updates.
- Message read receipts.

