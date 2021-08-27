import os
from twython import Twython, TwythonError
from flask import abort, Flask, jsonify, request
# adding random line to auth into github
# Flask webserver for incoming traffic from Slack
app = Flask(__name__)

# Helper for verifying that requests came from Slack
def is_request_valid(request):
    is_token_valid = request.form['token'] == os.environ['SLACK_VERIFICATION_TOKEN']
    is_team_id_valid = request.form['team_id'] == os.environ['SLACK_TEAM_ID']

    return is_token_valid and is_team_id_valid

@app.route('/', methods=['POST'])
def swaybot():

    # Verify correct Slack credentials
    if not is_request_valid(request):
        abort(400)

    # Authenticate into Twitter
    APP_KEY = os.environ['APP_KEY']
    APP_SECRET = os.environ['APP_SECRET']
    twitter = Twython(APP_KEY, APP_SECRET, oauth_version=2)
    ACCESS_TOKEN = twitter.obtain_access_token()
    twitter = Twython(APP_KEY, access_token=ACCESS_TOKEN)

    # Basic spell checker for valid twitter screen names
    def valid_user(name):
        try:
            user = twitter.lookup_user(screen_name=name)
            return True
        except TwythonError as e:
            return False

    # Save user input from /sway slash command
    incoming_text = request.form['text']

    if valid_user(incoming_text):

        def get_timeline(name,count=200):
            """Requests up to the last 200 Twitter statuses within a user's timeline"""
            timeline = twitter.get_user_timeline(screen_name=name,include_rts=False,exclude_replies=True,count=count)
            n = len(timeline)
            return timeline, n

        def user_info(name):
            """Looksup twitter profile and returns screen name and number of followers"""
            user = twitter.lookup_user(screen_name=name)
            screen_name = user[0]['screen_name']
            followers = user[0]['followers_count']
            return screen_name, followers

        def reactions(timeline):
            """Sum of all RT's and Favorites in the user's timeline"""
            rt_count = []
            fav_count = []
            for status in timeline:
                rt = status['retweet_count']
                fav = status['favorite_count']
                rt_count.append(rt)
                fav_count.append(fav)
            return sum(rt_count),sum(fav_count)

        def engagement(name,*args):
            """Calculates average RT's and Favorites"""
            # todo: add replies as a metric of engagement
            # todo: consider combining this function with reactions()
            # todo: that may make influence_model unnecessary
            timeline,n = get_timeline(name)
            screen_name,followers = user_info(name)
            rt_count, fav_count = reactions(timeline)
            return screen_name,followers,(int(rt_count/n)),(int(fav_count/n)),n

        def influence_model(name):
            """Simply calls engagement()"""
            args = [get_timeline,user_info,reactions]
            return engagement(name,args)

        def main(name):
            """Returns stats from engagement()"""
            user, followers, avg_rt, avg_fav, num_statuses = influence_model(name)
            data = jsonify(
                response_type='in_channel',
                text='User: {}\nFollowers: {}\nAverage Retweets: {}\nAverage Favorites: {}\n# of statuses: {}\n'.format(
                user, followers, avg_rt, avg_fav, num_statuses),
            )
            return data

        return main(incoming_text)

    else:
        return jsonify(
            response_type='in_channel',
            text="Whoops, that's not a real Twitter screen name. Try again.")
