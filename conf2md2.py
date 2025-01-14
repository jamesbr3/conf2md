#
# Confluence to Markdown converter
#
# Requires Python 3.5+
# see requirements.txt for Python dependencies
#
# Specify username and password (API token) in environment variables:
#   ATLASSIAN_USER=you@example.com
#   ATLASSIAN_TOKEN=xxxxxxx
#
# Obtain an API token from: https://id.atlassian.com
#   Security -> API token -> Create and manage API tokens
#
import requests
from dataclasses import dataclass
from requests.auth import HTTPBasicAuth
import json
import re
import html2text
import argparse
import os
import io
import shutil
import types

try:
    from getpass import getpass
except:
    def getpass(message): return raw_input(message)


@dataclass
class PageParts:  
  space: str
  contentid: str
  title: str = ''
  confuri: str = ''

class Confluence(object):

  def __init__(self, uri, user, authToken):
    self.base = uri
    self.creds = (user,authToken)
    self.headers = {
      'Content-Type': 'application/json'
    }
    pass

  def apiuri(self, uri):
    return self.base + '/wiki/api/v2/' + uri#/rest/api/' + uri

  def url_parts(uri):
    rx = re.compile(r"(http[s*]:\/\/.+\/wiki)\/spaces\/(\w+)\/pages\/(\d+)\/(.+)")
    m = rx.match(uri)
    if not m:
      raise UrlError(f"invalid Confluence URI: {uri}")
  
    return PageParts(
      confuri   = m.group(1),
      space     = m.group(2),
      contentid = m.group(3)
    )    

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
    uri = self.apiuri(f'content/{pageid}')
    params = {'expand': f"body.{view}"}
    r = requests.get(uri, params=params, auth=self.creds, headers=self.headers)
    j = json.loads(r.text)
    #self.dumpjson(r)
    return j['body'][view]['value']

  def grab_binary(self, url, outf):
    #urllib.request.urlretrieve("http://example.com", "file.ext")
    r = requests.get(url, headers=self.headers, auth=self.creds, stream=True)
    with open('img.png', 'wb') as out_file:
      r.raw.decode_content = True
      shutil.copyfileobj(r.raw, out_file)
      
      #out_file.write(r.raw)#r.raw.decode_content = True

  def images(self, pageid):
    uri = self.apiuri(f'content/{pageid}/child')
    params = {'expand': ['attachment']}
    r = requests.get(uri, params=params, auth=self.creds,headers=self.headers)
    j = json.loads(r.text)
    #print(json.dumps(j, indent=2))
    #print(r.text)
    return [
      PageParts(
        confuri = cpp.confuri,
        space   = cpp.space,
        title   = result['title'],
        contentid = result['id']
        )# if result['metadata']['mediaType'] == 'image/png'
        for result in j['attachment']['results'] 
    ]
    

  def children(self, pageid):
    #uri = self.apiuri(f'content/{pageid}/child')
    uri = self.apiuri(f'/pages/{pageid}/children')
    params = {'expand': ['page']}
    r = requests.get(uri, params=params, auth=self.creds,headers=self.headers)
    print(r.text)
    j = json.loads(r.text)
    #print(json.dumps(j, indent=2))
    
    
    return [
      PageParts(
        confuri = cpp.confuri,
        space   = cpp.space,
        title   = result['title'],
        contentid = result['id']
        )# if result['metadata']['mediaType'] == 'image/png'
        for result in j['page']['results'] 
    ]


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

def treeimg(level):
  if level == 0:
    return '0'
  if level == 1:
    return f'{level}├─'
  if level > 1:
    return f'{level}├─' + '──'*(level-1)

def print_treepart(s, nodech, fillch):
  print(nodech + fillch*3, file=s, end='')


def reverse_chunks(s, k):
  f=lambda s,n:s and f(s[n:],n)+s[:n]
  return f(s,k)

  #return ''.join(list(map(''.join, zip(*[iter(s)]*k))).reverse())
  #  return ''.join(s[i:i+k][::-1] for i in range(0, len(s), k))

def print_treelines(levelp):
  s = io.StringIO()
  if(levelp.hassibling):
    print_treepart(s, '├', '─')
  else:
    print_treepart(s, '└', '─')

  levelp = levelp.parent
  while(levelp):
    if(levelp.hassibling):
      print_treepart(s, '│', ' ')
    else:
      print_treepart(s, ' ', ' ')
    levelp = levelp.parent
  s.seek(0)
  return reverse_chunks(s.read(), 4)

def fixup_images(conf, html_string, levelp = None):
  #level = types.SimpleNamespace(
  # # haschildren = False,
  #  parent = levelp
  #)
  prefix = print_treelines(levelp)
  from bs4 import BeautifulSoup
  soup = BeautifulSoup(html_string, features="html.parser")

  images = soup.findAll('img')
  for idx,img in enumerate(images):
    #imgid = 
    rx = re.compile(r"\/(\d+)\/")
    m = rx.match(img['src'])
    imgid = m.group[1] if m else '?'

    #level = types.SimpleNamespace(
    #  hassibling = idx<len(images)-1,
    #  parent = levelp
    #)
    prefix = print_treelines(levelp)    
    print(f"Images:  {prefix}++++{imgid}")

    #conf.grab_binary(img['src'], 'oof')
    #img['src'] = 'img.png'
  
  return str(soup)

def grab_page(conf, cpp, recurse = True, levelp = None, hassibling=False):#space, pageid):
  #conf = Confluence(cpp.confuri, args.username, args.password)

  children_list = conf.children(cpp.contentid)
  #if len(children_list) > 0 and levelp:
  #  levelp.haschildren = True
  image_list = conf.images(cpp.contentid)
  
  #if len(children_list) > 0 and levelp or image_list and len(image_list)>0 and levelp:
  #  levelp.haschildren = True
  level = types.SimpleNamespace(
    hassibling = hassibling,
    parent = levelp
  )

  #print(children_list)

  prefix = print_treelines(level)
  print(f'Pulling: {prefix}[{cpp.contentid}]: {cpp.title}')

  
  html = conf.get_content(cpp.space, cpp.contentid, "view")  

  html_string = fixup_images(conf, html, level)

  # see: https://github.com/Alir3z4/html2text/blob/master/docs/usage.md
  h2t = html2text.HTML2Text()
  h2t.bypass_tables = False#True
  h2t.ignore_images = False
  md = h2t.handle(html_string)
  #print(md)

  for idx, child in enumerate(children_list):# conf.children(cpp.contentid):
    #level.hassibling 
    hs = idx < len(children_list)-1
    grab_page(conf, child, levelp = level, hassibling=hs)#level+1)

  




#def grab_page(url):
#  pass



if __name__ == "__main__":

  parser = argparse.ArgumentParser('Confluence to Markdown converter')
  parser.add_argument('--uri',        help = 'URI to confluence page')
  parser.add_argument('--username',   help = 'Username (must specify if ')
  parser.add_argument('--password',   help = 'Password')
  #parser.add_argument('--space',      help = 'Space')
  #parser.add_argument('--id',         help = 'Content ID')

  args = parser.parse_args()  

  args.uri = 'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/1967784829/Security+Bug+Fix+Policy'
  args.uri = 'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/3841458249/Security+Issue+Handling'
  args.uri = 'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/3845652552/Vulnerability+Management'
  if not args.username:
    args.username = os.environ.get('ATLASSIAN_USERNAME')
  if not args.username:
    print('Please specify --username or ATLASSIAN_USERNAME environment')
    sys.exit(0)

  if not args.password:
    args.password = os.environ.get('ATLASSIAN_PASSWORD')
  if not args.password:
    args.password = getpass.getpass(f'API token for {args.username}: ')

  
  if not args.uri:
    print("must specify --uri")#, or [--space and --content]")
    exit(1)  
  
  if not verify_creds(args):
    exit(1)    

  cpp = Confluence.url_parts(args.uri)
  conf = Confluence(cpp.confuri, args.username, args.password)
    

  grab_page(conf, cpp)
  