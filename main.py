import pandas as pd
import os
from fastapi import FastAPI, Query, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from dotenv import load_dotenv
import httpx
import base64

load_dotenv() # load .env variables

# attachment handling
pdf_file_path = os.getenv("ATTACHMENT_FILE")
pdf_display_name = os.getenv("ATTACHMENT_DISPLAY_NAME")

app = FastAPI()
user_sessions = {} # in-memory session (keyed by user email)

# auth code
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPES = "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/User.Read offline_access"

# allow the frontend to access this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ----------------- UTILITY FUNCTIONS -----------------
def read_pdf_as_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()
    
# fetch rows based on the email entered by the user
def load_assignments():
    assignments = {}
    df = pd.read_excel("files/recipients.xlsx")
    for i, row in df.iterrows():
        # skip rows where 'email_sent' in True
        if row.get('email_sent', False)==True or row.get('email_sent', False)=='TRUE':
            continue

        sender_email = row["Email"].strip().lower()
        if sender_email not in assignments:
            assignments[sender_email] = []
        assignments[sender_email].append({
            "recipient_fname": row["Vārds / First Name"],
            "recipient_lname": row["Uzvārds / Last Name"],
            "recipient_email": row["E-pasta adrese / Email Address"],
            "sender_name": row["Name"].split(" ")[0],
            "row_index": i      # save row index to update recipients.xlsx later
        })
    return assignments, df

def mark_emails_sent(df, sent_rows_indices):
    for idx in sent_rows_indices:
        df.at[idx, 'email_sent'] = 'TRUE'
    df.to_excel("files/recipients.xlsx", index=False)

assignments, df_recipients = load_assignments()

# ----------------- ROUTES -----------------
# /login route
@app.get("/login")
def login():
    auth_url = (
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_mode=query"
        f"&scope={SCOPES}"
    )
    return RedirectResponse(auth_url)

# /auth/callback route
@app.get("/auth/callback")
async def auth_callback(request: Request):
    code = request.query_params.get("code")
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

    data = {
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_secret": CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        token_data = response.json()

    access_token = token_data.get("access_token")
    if not access_token:
        return {"error": "Failed to get access token", "details": token_data}
    
    # get user's email using Graph
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        me = await client.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        print("Graph API status:", me.status_code)
        profile = me.json()
        print("Graph API response:", profile)

    user_email = profile.get("mail") or profile.get("userPrincipalName")
    
    # Check that user_email has been fetched successfully
    if not user_email:
        print("DEBUG: No email found in profile:", profile)
        return {"error": "Unable to retrieve your email from Microsoft. Please check your Microsoft account."}

    # Store access token
    user_sessions[user_email.lower()] = access_token

    return RedirectResponse(url=f"http://127.0.0.1:5500/index.html?user_email={user_email}")

# fetch recipients
@app.get("/recipients")
def get_recipients(user_email: str=Query(...)):
    user_email = user_email.strip().lower()

    # check if user is authenticated
    if user_email.lower() not in user_sessions:
        return JSONResponse(status_code=403, content={"error": "Missing or expired token."})

    recipients = assignments.get(user_email, [])
    sender_name = recipients[0]["sender_name"] if recipients else None
    print("Searching for:", user_email)
    print("Available:", list(assignments.keys()))
    return {"sender_name": sender_name, "recipients": recipients}

# load email text
@app.get("/email-template")
def get_email_template():
    try:
        with open("files/email_template.txt", "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse(content={"template": content})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# send emails
@app.post("/send-emails")
async def send_emails(user_email: str = Query(...), payload: dict = Body(...)):
    email_body = payload.get("email_body", "")
    selected_emails = payload.get("selected_emails", [])

    access_token = user_sessions.get(user_email.lower())
    if not access_token:
        print("Missing or expired token!")
        return {"error": "User not logged in or token expired."}

    all_recipients = assignments.get(user_email.lower(), [])
    print(f"Found {len(all_recipients)} recipients")

    if not all_recipients:
        return {"error": "No recipients found for this email."}
    
    # filter recipients to only the selected ones
    recipients = [r for r in all_recipients if r["recipient_email"] in selected_emails]
    if not recipients:
        return {"error": "No selected recipients found."}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    sent_rows = []
    async with httpx.AsyncClient() as client:
        for person in recipients:
            # Fill in personalized placeholders
            personalised_body = email_body.replace("{recipient_fname}", person['recipient_fname']) \
                                        .replace("{recipient_lname}", person['recipient_lname']) \
                                        .replace("{sender_name}", person.get('sender_name', 'Sender'))
            paragraphs = personalised_body.split("\n\n")
            html_body = ''.join(
                            f'<p>{p.strip().replace(chr(10), "<br>")}</p>'  # chr(10) == \n
                            for p in paragraphs
                        )

            email_data = {
                "message": {
                    "subject": "Invitation to share your views",
                    "body": {
                        "contentType": "HTML",
                        "content": html_body
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": person["recipient_email"]}}
                    ],
                    "attachments": [
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": pdf_display_name,
                            "contentBytes": read_pdf_as_base64(pdf_file_path)
                        }
                    ]
                },
                "saveToSentItems": "true"
            }

            
            response = await client.post(
                    "https://graph.microsoft.com/v1.0/me/sendMail",
                    headers=headers,
                    json=email_data
                )
            
            if response.status_code == 202:  # success
                sent_rows.append(person["row_index"])

    if sent_rows:
        mark_emails_sent(df_recipients, sent_rows)

    return {"message": f"{len(recipients)} emails sent!"}
