# personalised-email-helper
This is a lightweight app to automate the distribution of personalised emails to a predefined set of recipients. 

Users can: 
1. authenticate through their institutional email,
2. preview, and possibly modify, the generated message, 
3. select recipients from a pre-assigned list, 
4. send personalised emails to the selected recipients.

## To use the app
### 1. (Fork and) clone the repo
```
git clone https://github.com/<username>/personalised-email-helper.git
cd personalised-email-helper
```

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Register the app on your email provider's dev portal (or equivalent)
For institutional emails, one can use (for example) Microsoft Azure App Registration to obtain the sensitive information (client secrets, client id, etc) necessary to enable user authentication and email distribution from their _own_ email addresses.

### 4. Update `.env.example` with credentials
Update the `.env.example` file with your credentials and ⚠️**rename the file to `.env`** to ensure the sensitive information does not get committed.

### 5. Specify attachment path and display name
To replace the placeholder attachment (`files/attachment-example.pdf`), add your own pdf file to the repo and update the file path and display name in `.env`. Update `.gitignore` if you do not wish to commit the pdf file. Only pdf attachments are supported at the moment.

### 6. Provide default email text
To modify the placeholder email text, update `files/email_template-example.txt` and ⚠️**rename the file to `files/email_template.txt`** to ensure this file gets used and the information it contains does not get committed. Currently, the only personalisations supported by the app are the recipient's first name (`fname`) and the sender's first name (`sender_name`). 

### 7. Add recipient information
Add key information of the sender (name, email) and the recipients (name, email) to `files/recipients-example.xlsx` and ⚠️**rename the file to `files/recipients.xlsx`** to ensure the file gets used correctly and the information it contains does not get committed.

### 8. Run the app locally
To start the backend, navigate to the project folder and run:
```
uvicorn main::app --reload
```

To start the frontend, navigate to the `/frontend` subfolder in the project folder and run:
```
python –m http.server 5500
```

Then open `localhost:5500` in your browser.


