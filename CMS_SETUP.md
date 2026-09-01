# Admin CMS Setup

The site now includes a hidden Decap CMS admin page at:

`https://sdiaeyu6n.github.io/admin/`

It is not linked from the public navigation. Anyone can type the URL, but only an authenticated GitHub user with write access to `sdiaeyu6n/sdiaeyu6n.github.io` can publish changes.

## What Is Already Configured

- Admin page: `admin/index.html`
- CMS config: `admin/config.yml`
- Blog posts collection: `_posts`
- Uploaded images folder: `images/blog`
- GitHub repo backend: `sdiaeyu6n/sdiaeyu6n.github.io`
- Branch: `master`

## GitHub OAuth Setup

GitHub Pages is static hosting, so it cannot securely handle GitHub OAuth by itself. Decap CMS needs an OAuth service between the browser and GitHub.

The simplest setup is to use Netlify only as the OAuth provider while keeping the actual website hosted on GitHub Pages.

1. Go to GitHub Developer Settings:
   `https://github.com/settings/developers`
2. Create a new OAuth App.
3. Use these values:
   - Application name: `Sieun Choi Website CMS`
   - Homepage URL: `https://sdiaeyu6n.github.io`
   - Authorization callback URL: `https://api.netlify.com/auth/done`
4. Copy the GitHub OAuth `Client ID` and create/copy a `Client Secret`.
5. In Netlify, create any small site. It does not need to host this website.
6. In that Netlify site, go to site configuration, access/security, OAuth, then install the GitHub authentication provider.
7. Paste the GitHub OAuth `Client ID` and `Client Secret`.
8. Add `sdiaeyu6n.github.io` as a domain/site domain in that Netlify OAuth setup if Netlify asks for it.
9. After the website is pushed and deployed, visit:
   `https://sdiaeyu6n.github.io/admin/`

Only GitHub users with write access to `sdiaeyu6n/sdiaeyu6n.github.io` can publish changes through the CMS.

## Alternative OAuth Proxy

If you do not want to use Netlify for authentication, deploy a Decap-compatible GitHub OAuth proxy on Cloudflare Workers, Vercel, or another backend. Then add its URL to `admin/config.yml`:

```yml
backend:
  name: github
  repo: sdiaeyu6n/sdiaeyu6n.github.io
  branch: master
  base_url: https://your-oauth-proxy.example.com
```

## Writing Posts

After login works, go to `/admin/`, choose `Blog Posts`, and create a new post. The CMS will create Markdown files in `_posts` and upload images to `images/blog`.
