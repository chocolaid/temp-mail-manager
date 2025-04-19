# Temp Mail API

A simple API for creating and managing temporary email addresses using Puppeteer.

## Features

- Create temporary email addresses
- Check inbox for received emails
- Session management
- Rate limiting
- Production-ready configuration

## API Endpoints

### Create Email
```http
GET /create-email
```
Creates a new temporary email address and returns a session ID.

Response:
```json
{
  "sessionId": "d3d67f86-266c-405f-bd93-ea01d25a0a4a",
  "email": "1r4m6rtaa8@mrotzis.com"
}
```

### Get Inbox
```http
GET /get-inbox/:sessionId
```
Retrieves emails for a specific session.

Response:
```json
{
  "inbox": [
    {
      "from": "sender@example.com",
      "date": "2024-03-14",
      "subject": "Test Email",
      "snippet": "Hello..."
    }
  ]
}
```

### Kill Session
```http
GET /kill-session/:sessionId
POST /kill-session/:sessionId
```
Closes the browser session and cleans up resources.

Response:
```json
{
  "message": "Session killed successfully"
}
```

## Setup

1. Clone the repository
2. Install dependencies:
```bash
npm install
```

3. Start the server:
```bash
npm start
```

## Environment Variables

- `PORT`: Server port (default: 3000)
- `NODE_ENV`: Environment (development/production)

## Railway.app Deployment

This application is optimized for deployment on Railway.app. It includes:

- Health check endpoint (`/health`)
- Graceful shutdown handling
- Production-ready configuration
- Proper logging

## Security

- Rate limiting (200 requests per 15 minutes)
- Helmet.js for security headers
- Input validation
- Session management

## License

MIT 