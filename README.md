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
  - set Gmail query to be the desired amount of days to search through (testing > 2d, running = 1d)
  - Add account methods below gmail query. Place your "bobsmith123" email in the method to pass so that it can find your file. Multiple methods in that list are fine
  - edit logger.setLevel to "logging.WARNING" once you are ready to push to aftership, leave in DEBUG till then 
  - set "run_cleanup" to TRUE if you want to delete any "delivered" packages as these won't be automatically removed from aftership (that i know of)

Note:
  - Gmail Oauth will require a browser to log in or use the link provided in the console. this will generate a .pickle file that if used once a day will not require a re-log in
