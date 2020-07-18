# mail_to_aftership
Import tracking numbers from email into aftership

Small script to import email, parse for tracking numbers and forward tracking numbers to aftership. Wrote this so that [Magic Mirror 2](https://github.com/MichMich/MagicMirror) would be auto-updated with shipments. Currently supporting USPS, UPS, FEDEX, LASERSHIP.

Items needed to run:
  - [Aftership API Key](https://admin.aftership.com/settings/api-keys)
  - Gmail API Credentials.json file
  
How to run:
  - Place API key into python file for aftership
  - Enable the Gmail API on your account - [Here](https://developers.google.com/gmail/api/quickstart/python) 
  - Download the credentials.json and place it in the folder of the mail_import.py file
  - Rename gmail credentials.json to be "myemailaddressbeforethe@_credentials.json" (e.g. bobsmith123_credentials.json)
  - Set Gmail query to be the desired amount of hours/days to search through (testing > 2d, running = 1d or even 1h)
  - Add account(s) to gmail query list. Place your "bobsmith123" email in the method to pass so that it can find your file. Multiple emails in that list are fine. Make sure to copy the method "gmail_login("myemailaddressbeforthe@")" per account
  - Call script with the following paramater options
    - -s to search 
    - -d to set debug to true or false (true is default and will NOT upload search results, false will upload)
    - -c to run cleanup, the script will remove any "delivered" packages as these won't be automatically removed from aftership (that i know of)
    
Notes:
  - Gmail Oauth will require a browser to log in or use the link provided in the console on the first run. This will generate a .pickle file that, if used once a day, will not require a re-log in
  - Be cautious of when you run search and cleanup. Don't want have a broad search that gets cleaned up often consuming your free 50 tracking's per month
  - Tracking numbers that are currently in Aftership will not be re-uploaded. This means you can run the script more often with a broader search keeping in mind the above note about cleaning
  
Example tests/debugging:

- python3 mail_import.py -s -d true 
- python3 mail_import.py -s -d

Example 'production' usage with crontab:

- Running every hour to search for new tracking numbers
  - 0 * * * * python3 mail_import.py -s -d false

- Running at midnight to cleanup delivered packages 
  - 0 0 * * * python3 mail_import.py -c -d false

Example Note: You could run search and cleanup at the same time but this would only work well if run once a day as you
could potentially upload and cleanup the same tracking numbers every time the script is run which could quickly consume your 50 free tracking numbers per month
