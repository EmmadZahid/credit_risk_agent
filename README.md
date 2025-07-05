# credit_risk_agent

## Steps to run:

- Make sure to install Python and pip  
- Run `python -m venv venv`  
- Run `.\venv\Scripts\activate.bat` (on Windows)  
- Run `pip install -r requirements.txt`  
- Now go to the root folder and run `adk web`
- Go to `localhost:8000`
- For real emails, set environment variable `EMAIL_API_KEY` to valid SendGrid API Key
- For mock email setup, run this command: `docker run --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog`
- Check received emails at this url, open in browser: `http://localhost:8025/`
