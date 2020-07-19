from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from apiclient import errors
import base64
from io import StringIO
from html.parser import HTMLParser
import re
import aftership
import time
import sys
import getopt
import logging
# Default logging level for dependencies above. Google is a little chatty
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def gmail_login(email_id):
    # https://developers.google.com/gmail/api/quickstart/python
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    creds = None
    email_id = str(email_id)

    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(email_id+'_token.pickle'):
        with open(email_id+'_token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Please log in for email:" + email_id)
            flow = InstalledAppFlow.from_client_secrets_file(
                email_id+'_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(email_id+'_token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    print("Logged into " + email_id)
    return creds


def get_messages(query, creds_list):
    """
    Get messages from GMail based upon search query
    Parses the json to get just the body of the message both with parts and non-parts
    """
    trimmed_messages = {}
    for creds in creds_list:
        service = build('gmail', 'v1', credentials=creds)
        try:
            response = service.users().messages().list(userId='me', q=query).execute()
            messages_ids = []

            if 'messages' in response:
                # print(response)
                messages_ids.extend(response['messages'])

            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = service.users().messages().list(userId='me', q=query,
                                                           pageToken=page_token).execute()
                messages_ids.extend(response['messages'])

            for msg_id in messages_ids:
                message = service.users().messages().get(userId='me', id=msg_id['id']).execute()
                # pprint.pprint(message)
                body = ""
                if 'data' in message['payload']['body']:
                    body = str(base64.urlsafe_b64decode(message['payload']['body']['data']), 'utf-8')
                elif 'parts' in message['payload']:
                    for p in message['payload']['parts']:
                        body += str(base64.urlsafe_b64decode(p['body']['data']), 'utf-8')
                else:
                    logging.error("had issues with message: " + str(message))
                    logger.debug('data' in message['payload']['body'])
                    logger.debug('parts' in message['payload'])
                    logger.debug(message.keys())
                    logger.debug(message['payload']['body'].keys())
                    logger.debug(message['payload']['body'].values())

                # search for the "from" field and pull out the sender to title the shipment. if no sender, use msg_id
                title = next((i['value'] for i in message['payload']['headers'] if i["name"] == 'From'), msg_id)

                # i'd include this above but then it would just be too awesome of a one liner
                if "\"" in title:
                    title = title.split('"')[1]

                trimmed_messages[title] = (strip_tags(body))

        except errors.HttpError as error:
            logging.error('An error occurred: %s' % error)

    return trimmed_messages


def cleanup_tracking(tracking_id=None):
    try:
        result = aftership.tracking.list_trackings(tag="Delivered")
    except aftership.exception.NotFound:
        logger.debug("No tracking numbers are 'delivered' yet, this is fine")
        return None

    for tracking in result['trackings']:
        try:
            aftership.tracking.delete_tracking(tracking_id=tracking['id'])
        except aftership.exception.NotFound:
            logger.warning(tracking_id + " was returned from the site but could not be deleted... :shrug:")

    return True


def search_messages(messages, grab_only_first_match=True):
    nums = {}
    # Currently used:
    # https://andrewkurochkin.com/blog/code-for-recognizing-delivery-company-by-track
    # you could also try this YMMV:
    # https://stackoverflow.com/questions/619977/regular-expression-patterns-for-tracking-numbers
    # Another resource - Look under "others" for tracking formats:
    # https://www.trackingmore.com/tracking-status-en.html
    usps_pattern = [
        '(?:94|93|92|94|95)[0-9]{20}',
        '(?:94|93|92|94|95)[0-9]{22}',
        '(?:70|14|23|03)[0-9]{14}',
        '(?:M0|82)[0-9]{8}',
        '(?:[A-Z]{2})[0-9]{9}(?:[A-Z]{2})'
    ]

    ups_pattern = [
        '(?:1Z)[0-9A-Z]{16}',
        '(?:T)+[0-9A-Z]{10}',
        '[0-9]{26}'
    ]

    fedex_pattern = [
        '[0-9]{20}',
        '[0-9]{15}',
        '[0-9]{12}',
        '[0-9]{22}'
    ]

    lasership_pattern = [
        '(?:1LS)[0-9]{12}',
        '(?:LX)[0-9]{8}',
        '(?:LW)[0-9]{8}'
    ]

    usps = "(" + ")|(".join(usps_pattern) + ")"
    fedex = "(" + ")|(".join(fedex_pattern) + ")"
    ups = "(" + ")|(".join(ups_pattern) + ")"
    ls = "(" + ")|(".join(lasership_pattern) + ")"

    patterns = {"usps": usps, "fedex": fedex, "ups": ups, "lasership": ls}

    # look through all the messages
    for subject, msg in messages.items():
        # get rid of extra characters we don't need
        msg = msg.replace(" ", "").replace("\r\n", "")
        # look through all our patterns
        for company, pattern in patterns.items():
            # see if a pattern matches
            results = re.search(pattern, msg)
            # see if there is a match and the name of the company is the same as the matching pattern
            if results and company in msg.lower():
                logger.debug(results.groups())  # debug for the win!
                # look through the results for which pattern matched
                for match in results.groups():
                    # look for a match that isn't "None"
                    if match:
                        nums[match] = [company, subject]
                        # either grab the first match or grab all of them
                        if grab_only_first_match:
                            continue

        logger.warning("Didn't match on a message ")

    if len(nums) != len(messages):
        logger.warning("The Regex didn't match on a message that was given to it")

    return nums


def upload_nums(track_nums):
    # Create our request - https://help.aftership.com/hc/en-us/articles/115008491328-Locate-slug-for-a-courier
    for t_num, info in track_nums.items():
        tracking = {'slug': info[0], 'tracking_number': t_num, "title": info[1]}
        logger.debug(tracking)
        # if you want to test leave in debug above
        if logger.level is not logging.DEBUG:
            try:
                result = aftership.tracking.create_tracking(tracking=tracking, timeout=10)
                print("Uploaded tracking, result: " + str(result['tracking']['id']))
            except aftership.exception.BadRequest:
                logger.warning("Shipment already exists, skipping...")
        # just to keep aftership api happy
        time.sleep(1)
        logger.debug("Did not upload because you are debugging")


if __name__ == '__main__':

    # Get arguments
    # option for cleaning
    # option for debugging
    # option for running search
    debug = None
    cleanup = False
    search = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hsd:c", ["search", "debug", "cleanup"])
    except getopt.GetoptError as e:
        print(e)
        print('mail_import.py -s -d <true or false> -c')
        print('Set either -s or -c to search or cleanup. -d flag is always needed')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('mail_import.py -d <true or false> -c ')
            sys.exit()
        elif opt in ("-s", "--search"):
            print("Searching mail")
            search = True

        elif opt in ("-d", "--debug"):
            try:
                if arg == 'false':
                    print("Debug set to Warning, will send to Aftership if you are searching")
                    debug = logging.WARNING
                else:
                    print("Debug set to Debug, will NOT send to Aftership if you are searching")
                    debug = logging.DEBUG

                logger.setLevel(debug)
            except Exception as e:
                print(e)
                sys.exit(2)
        elif opt in ("-c", "--cleanup"):
            print("Running cleanup")
            cleanup = True

    if not debug:
        print("Debug flag not set")
        sys.exit()

    if search:
        # Aftership API Key - https://www.aftership.com/
        aftership.api_key = "YOUR-API-KEY"
        # Gmail search query - https://support.google.com/mail/answer/7190?hl=en
        # most shipping companies won't track items beyond 120days (good to test your search with though)
        # better to do 1d or 1h
        q = "in:inbox (+tracking +fedex|usps|ups|lasership) newer_than:7d"
        # How many accounts you want to add.
        # Additional methods to list will add more accounts (seperate API keys/pickle files needed)
        # https://developers.google.com/gmail/api/quickstart/python
        c = [gmail_login("myemailaddressbeforthe@"), gmail_login("myemailaddressbeforthe@2"),
             gmail_login("myemailaddressbeforthe@3")]
        # Obtain our messages for all of our accounts
        msgs = get_messages(q, c)
        if len(msgs) > 0:
            logger.debug("Messages found: " + str(len(msgs)))
            # parse email bodies for tracking numbers
            t_nums = search_messages(msgs)
            # upload numbers to aftership
            upload_nums(t_nums)
        else:
            print("No messages found with search query, maybe you haven't received any emails with tracking recently?")

    # running this after to make sure we don't delete and then re-upload. Skipping this while testing is recommended.
    # best to run cleanup daily as a seperate cronjob, etc
    if cleanup:
        cleanup_tracking()
