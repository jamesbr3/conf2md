#
# Confluence to Markdown converter
#
# Requires Python 3.5+
# see requirements.txt for Python dependencies
#
# Specify username and password (API token) in environment variables:
#   ATLASSIAN_TOKEN=you@example.com
#   ATLASSIAN_TOKEN=xxxxxxx
#
# Obtain an API token from: https://id.atlassian.com
#   Security -> API token -> Create and manage API tokens
#
import requests
from requests.auth import HTTPBasicAuth
import json
import re
import html2text
import argparse
import os

try:
    from getpass import getpass
except:
    def getpass(message): return raw_input(message)

class Confluence(object):

  def __init__(self, uri, user, authToken):
    self.base = uri
    self.creds = (user,authToken)
    self.headers = {
      'Content-Type': 'application/json'
    }
    pass

  def apiuri(self, uri):
    return self.base + '/rest/api/' + uri

  def dumpjson(self,j):
    j = json.loads(j)
    print(json.dumps(j, indent=4, sort_keys=True))
    pass

  def lookup_content(self, space, title):
    url = self.apiuri('content')
    params = f"spaceKey={space}&title={title}&expand=body"
   
    r = requests.get(url, params=params, auth=self.creds, headers=self.headers)
    j = json.loads(r.text)
    #self.dumpjson(r.text)
    return j['results'][0]['id']

  def get_content(self, space, pageid, view='storage'):
    uri = self.apiuri('content/'+pageid)
    params = {'expand': f"body.{view}"}
    r = requests.get(uri, params=params, auth=self.creds, headers=self.headers)
    j = json.loads(r.text)
    #self.dumpjson(r)
    return j['body'][view]['value']

def verify_creds(args):
  if not args.username and 'ATLASSIAN_USER' in os.environ:
    args.username = os.environ['ATLASSIAN_USER']

  if not args.username:
    print("--username required")
    return False    

  if not args.password and 'ATLASSIAN_TOKEN' in os.environ:
    args.password = os.environ['ATLASSIAN_TOKEN']    

  if not args.password:
    args.password = getpass("Password: ")

  if not args.password:
    print("--password required")
    return False

  return True

if __name__ == "__main__":

  parser = argparse.ArgumentParser('Confluence to Markdown converter')
  parser.add_argument('--uri',        help = 'URI to confluence page')
  parser.add_argument('--username',   help = 'Username (must specify if ')
  parser.add_argument('--password',   help = 'Password')
  #parser.add_argument('--space',      help = 'Space')
  #parser.add_argument('--id',         help = 'Content ID')

  args = parser.parse_args()  
  
  if not args.uri:
    print("must specify --uri")#, or [--space and --content]")
    exit(1)  
  
  rx = re.compile(r"(http[s*]:\/\/.+\/wiki)\/spaces\/(\w+)\/pages\/(\d+)\/(.+)")
  m = rx.match(args.uri)
  if not m:
    print("invalid Confluence URI")
    exit(1)
  
  confuri   = m.group(1)
  space     = m.group(2)
  contentid = m.group(3)

  if not verify_creds(args):
    exit(1)    

  conf = Confluence(confuri, args.username, args.password)
  html = conf.get_content(space, contentid, "view")

  # see: https://github.com/Alir3z4/html2text/blob/master/docs/usage.md
  h2t = html2text.HTML2Text()
  h2t.bypass_tables = True
  h2t.ignore_images = False
  md = h2t.handle(html)

  print(md)
