# conf2md
Confluence to Markdown converter

## Usage

```
python conf2md.py --username <username> --uri <Content-URI> 
```

Where Content-URI is of the form: `https://example.atlassian.net/wiki/spaces/SPACE/pages/ID/TITLE`

* `username` can be stored as an environment variable `ATLASSIAN_USER`
* `password` can be stored as an environment variable `ATLASSIAN_TOKEN`. If it is not found, conf2md will prompt you for it

## API token

A Confluence API token can be obtained from https://id.atlassian.com

Navigate to Security -> API token -> Create and manage API tokens

It is recommended to use an API token (instead of your password) if this script is automated in any way

