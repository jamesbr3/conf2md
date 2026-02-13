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
from html2text import html2text
import requests
from attrs import define
from requests.auth import HTTPBasicAuth
import json
import re
#import html2text
import argparse
import os
import io
import shutil
import types
import sys
import pathlib
from pathlib import PurePosixPath

from markdownify import ATX
from markdownify import MarkdownConverter

try:
    from getpass import getpass
except:
    def getpass(message): return raw_input(message)


@define
class UrlParts:  
  space: str
  contentid: str
  title: str = ''
  confuri: str = ''

  @property
  def filename(self):
    #return f"{self.title}.md"
    #Remove invalid filename characters (Windows, Linux, macOS safe)
    s = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', self.title)
    # Optionally, strip leading/trailing whitespace and dots
    s = s.strip().strip('.')
    # Limit length if needed (e.g., 255 chars)
    return s[:255]

@define
class Page:
  id: str
  title: str
  content: str = None
  children: list = []
  ancestors: list = []
  @property
  def filename(self):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', self.title)
    s = s.strip().strip('.')
    return s[:255]

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

  def url_parts(uri):
    rx = re.compile(r"(http[s*]:\/\/.+\/wiki)\/spaces\/(\w+)\/pages\/(\d+)\/(.+)")
    m = rx.match(uri)
    if not m:
      raise UrlError(f"invalid Confluence URI: {uri}")
  
    return UrlParts(
      confuri   = m.group(1),
      space     = m.group(2),
      contentid = m.group(3),
      title     = m.group(4)
    )    

  def dumpjson(self,j):
    j = json.loads(j)
    print(json.dumps(j, indent=4, sort_keys=True))
    pass

  """
  def lookup_content(self, space, title):
    url = self.apiuri('content')
    params = f"spaceKey={space}&title={title}&expand=body"
   
    r = requests.get(url, params=params, auth=self.creds, headers=self.headers)
    j = json.loads(r.text)
    #self.dumpjson(r.text)
    return j['results'][0]['id']
  """
  def get_content_and_children(self, pageid, view='storage'):
    uri = self.apiuri(f'content/{pageid}')
    params = {'expand': f"body.{view},children.page,ancestors"}

    r = requests.get(uri, params=params, auth=self.creds, headers=self.headers)
    result = json.loads(r.text)
    return Page(
        title   = result['title'],
        id  = result['id'],
        content = result['body'][view]['value'],
        children = [Page(id=child['id'],title=child['title']) for child in result['children']['page']['results']],
        ancestors = [a['title'] for a in result['ancestors']]
        )

  """
  def get_content(self, pageid, view='storage'):
    uri = self.apiuri(f'content/{pageid}')
    params = {'expand': f"body.{view},children.page"}
    r = requests.get(uri, params=params, auth=self.creds, headers=self.headers)
    j = json.loads(r.text)
    #result = j['page']['results']
    #self.dumpjson(r)
    return j['body'][view]['value']
  """
  def grab_binary(self, url, outf='img.png', content_type='application/octet-stream'):
    #urllib.request.urlretrieve("http://example.com", "file.ext")
    # Don't set Content-Type for GET requests - let the server determine it
    headers = {}
    r = requests.get(url, headers=headers, auth=self.creds, stream=True)
    
    # Check for authentication errors
    if r.status_code == 401:
      print(f"Authentication failed for URL: {url}")
      print(f"Using credentials for base: {self.base}")
      print(f"Response: {r.text}")
      return
    elif r.status_code != 200:
      print(f"Failed to download {url}: Status {r.status_code}")
      print(f"Response: {r.text}")
      return
      
    pathlib.Path(outf).parent.mkdir(parents=True, exist_ok=True) 
    with open(outf, 'wb') as out_file:
      r.raw.decode_content = True
      shutil.copyfileobj(r.raw, out_file)
      
      #out_file.write(r.raw)#r.raw.decode_content = True

  """
  def images(self, pageid):
    uri = self.apiuri(f'content/{pageid}/child')
    params = {'expand': ['attachment']}
    r = requests.get(uri, params=params, auth=self.creds,headers=self.headers)
    j = json.loads(r.text)
    #print(json.dumps(j, indent=2))
    #print(r.text)
    return [
      UrlParts(
        confuri = cpp.confuri,
        space   = cpp.space,
        title   = result['title'],
        contentid = result['id']
        )# if result['metadata']['mediaType'] == 'image/png'
        for result in j['attachment']['results'] 
    ]
  """  

  def ancestors(self, pageid):
    uri = self.apiuri(f'content/{pageid}')
    params = {'expand': 'ancestors'}
    r = requests.get(uri, params=params, auth=self.creds,headers=self.headers)
    j = json.loads(r.text)

    parts = [a['title'] for a in j['ancestors']]
    return parts + [j['title']]

  def children(self, pageid):
    uri = self.apiuri(f'content/{pageid}/child')
    params = {'expand': ['page']}
    r = requests.get(uri, params=params, auth=self.creds,headers=self.headers)
    j = json.loads(r.text)
    #print(json.dumps(j, indent=2))
    #print(r.text)
    
    return [
      UrlParts(
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

def fixup_images(conf, html_string, levelp = None, hassibling=False,dir='', imgprefix=''):
  
  prefix = print_treelines(levelp)
  from bs4 import BeautifulSoup
  soup = BeautifulSoup(html_string, features="html.parser")


  images = soup.find_all('img')
  for idx,img in enumerate(images):
    #imgid = 
    rx = re.compile(r"\/(\d+)\/")
    src = img.get('data-image-src', img['src'])
    #m = rx.search(img['src'])
    #imgid = m.group(1) if m else '?'
    if 'data-linked-resource-id' not in img.attrs:
      print(f"Warning: image missing data-linked-resource-id attribute: {src}")
      continue
    else:
      imgid = img['data-linked-resource-id']

    if 'data-linked-content-type' in img.attrs:
      content_type = img.attrs['data-linked-content-type']
      content_extn = '.' + content_type.split('/')[-1]
    else:
      content_type = 'image/png' # default?
      content_extn = '.png'

    if not content_type.startswith('image/'):
      print(f"Skipping non-image content: {content_type}: {src}")
      continue
    #imgid = re.sub(r'\D', '', src)

    level = types.SimpleNamespace(
      hassibling = idx<len(images)-1 or hassibling,
      parent = levelp
    )
    prefix = print_treelines(level)    
    print(f"Images:  {prefix}[{imgid}{content_extn}]")

    outf = os.path.join(dir, imgid+content_extn)
    conf.grab_binary(src, outf, content_type)

    imgpath = PurePosixPath(imgprefix, imgid).with_suffix(content_extn)
    img['src'] = imgpath
  
  return str(soup)

def strip_common_ancestors(ancestors, page_ancestors):
    i = 0
    while i < len(ancestors) and i < len(page_ancestors) and ancestors[i] == page_ancestors[i]:
        i += 1
    return ancestors[i:]

def fixup_tables(conf, page, html_string):
  from bs4 import BeautifulSoup
  soup = BeautifulSoup(html_string, features="html.parser")

  telems = soup.find_all(['table', 'td', 'tr', 'th', 'tbody', 'thead'])
  for idx,te in enumerate(telems):
    te['markdown'] = '1'
  return str(soup)

def fixup_links(conf, page, html_string):

  from bs4 import BeautifulSoup
  soup = BeautifulSoup(html_string, features="html.parser")

  links = soup.find_all('a')
  for idx,link in enumerate(links):
    if 'data-linked-resource-type' in link.attrs and link['data-linked-resource-type'] == 'page':
      pageid = link['data-linked-resource-id']

      ancestors = conf.ancestors(pageid)
      ancestors = strip_common_ancestors(ancestors, page.ancestors + [page.title])
      
      pathstr = PurePosixPath('.', *ancestors, ancestors[-1]).with_suffix('.md')
      from urllib.parse import quote
      encoded = quote(str(pathstr))

      link['href'] = encoded
  
  return str(soup)

def convert_html_to_markdown(html_string, bypass_tables=False):#levelp=None):
  if 1:
    
    
    #from markdownify import markdownify as md
    from table_converter import TableConverter
    md = TableConverter()
    return md.convert(html_string)#, convert=['b'])  # > '**Yay** GitHub'
  else:
    #from markdownify import markdownify as md
    # See: https://github.com/Alir3z4/html2text/blob/master/docs/usage.md
    #
    h2t = html2text.HTML2Text()
    h2t.bypass_tables = bypass_tables#True#False#True
    h2t.ignore_images = False
    md = h2t.handle(html_string)
    return md


def grab_page(conf, pageid, recurse = True, levelp = None, hassibling=False, dir='',imgdir=None, imgprefix='',outname=None, bypass_tables=False):#space, pageid):

  page = conf.get_content_and_children(pageid,"view")

  cdir = dir
  if '{ancestor_titles}' in dir:
    cdir = cdir.replace('{ancestor_titles}', os.path.join(*page.ancestors))
  
  if '{page_title}' in dir:
    cdir = cdir.replace('{page_title}', page.filename)
    
  #cdir = os.path.join(dir, *page.ancestors, page.filename)
  pathlib.Path(cdir).mkdir(parents=True, exist_ok=True) 
  level = types.SimpleNamespace(
    hassibling = hassibling,
    parent = levelp
  )

  prefix = print_treelines(level)
  print(f'Pulling: {prefix}[{page.id}]: {page.title}')


  #
  # Parse the HTML content and fix image links to be local files instead of URLs
  # Also download the images to the local directory
  #
  html_string = fixup_images(conf, page.content, levelp=level, hassibling=len(page.children)>0,dir=cdir if not imgdir else imgdir, imgprefix=imgprefix)

  html_string = fixup_links(conf, page, html_string)

  if bypass_tables:
    html_string = fixup_tables(conf, page, html_string)

  #
  # Convert HTML to Markdown
  md = convert_html_to_markdown(html_string)#, levelp=level)


  filename = outname if outname else page.filename+'.md'
  path = os.path.join(cdir, filename)

  with open(path, 'wt', encoding='utf-8') as f:
    f.write(md)
  #print(md)

  if recurse:
    for idx, child in enumerate(page.children):# conf.children(cpp.contentid):
      #level.hassibling 
      hs = idx < len(page.children)-1
      grab_page(conf, child.id, levelp = level, hassibling=hs, dir=dir,imgdir=imgdir, imgprefix=imgprefix, outname=None)#os.path.join(dir, cpp.filename))

  


if __name__ == "__main__":

  parser = argparse.ArgumentParser('Confluence to Markdown converter')
  parser.add_argument('--uri',        help = 'URI to confluence page(s)', nargs='+')
  #parser.add_argument('--page',        help = 'Page ID(s)', nargs='+')
  parser.add_argument('--username',    help = 'Username (must specify if ')
  parser.add_argument('--password',    help = 'Password')
  
  # Create mutually exclusive group for recurse and outname
  group = parser.add_mutually_exclusive_group()
  group.add_argument('--recurse',      help = "Recursively process child pages", action='store_true')
  group.add_argument('--outname',      help = "Output filename(s) (optional list of filenames)", nargs='*', default=None)
  
  parser.add_argument('--outdir',      help = "Base output directory", required=False, default='out/{ancestor_titles}')
  parser.add_argument('--imgdir',      help = "Image directory", required=False, default=None)
  parser.add_argument('--imgprefix',   help = "Image prefix for markdown", required=False, default=None)

  parser.add_argument('--bypass-tables',   help = "Don't convert tables to markdown", required=False, action='store_true')

  # Parse an array of options instead of sys.argv
  option_array = ['--uri', 
                  'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/6275400419/CBUAE+PHASE+2+Security+Compliance+Design+Document+WIP', 
                  'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/1245479510/Vulnerability+Disclosure+Handling+Process',
                  'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/1967784829/Security+Bug+Fix+Policy',
                  '--outdir', 'out',
                  '--imgdir', 'out/img',
                  '--imgprefix', 'img/',
                  '--bypass-tables',
                  '--outname', 'output.md']
  args = parser.parse_args(option_array)  

  #args.uri = 'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/1967784829/Security+Bug+Fix+Policy'
  #args.uri = 'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/3841458249/Security+Issue+Handling'  
  #args.uri = 'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/4058873878/Corda+5+Research'
  #args.uri= 'https://r3-cev.atlassian.net/wiki/spaces/SEC/pages/3702456355/Corda+Security+Model+101'
  
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

  # Process each URI
  for idx, uri in enumerate(args.uri):
    cpp = Confluence.url_parts(uri)
    conf = Confluence(cpp.confuri, args.username, args.password)

    if args.outname:
      if len(args.outname) > idx:
        outname = args.outname[idx]
      else:
        from pathlib import Path
        base_path = Path(args.outname[0])
        outname = str(base_path.with_stem(f"{base_path.stem}_{idx}"))
    else:
      outname = None    
    
    grab_page(conf, cpp.contentid, dir=args.outdir, 
              recurse=args.recurse, 
              imgdir=args.imgdir, 
              imgprefix=args.imgprefix, 
              outname=outname, 
              bypass_tables=args.bypass_tables)
