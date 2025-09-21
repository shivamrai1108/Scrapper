# Reddit Scraper Pro - Multi-Tenant Slack App Deployment Guide

## 🎯 Overview

Reddit Scraper Pro is now a universal Slack app that supports multiple workspaces with individual OAuth installations, encrypted token storage, usage tracking, and billing management.

## 🏗️ Architecture

- **Multi-tenant**: Each workspace has its own encrypted tokens and settings
- **OAuth 2.0**: Secure installation flow with proper scopes
- **Usage tracking**: Per-workspace limits and billing analytics
- **Admin dashboard**: Complete management interface
- **Rate limiting**: Per-user hourly limits to prevent abuse

## 🚀 Deployment Steps

### 1. Create Slack App

1. Go to [Slack API Console](https://api.slack.com/apps)
2. Create a new app "Reddit Scraper Pro"
3. Configure OAuth & Permissions:
   - **Scopes**: `commands`, `chat:write`, `bot`, `users:read`, `channels:read`, `groups:read`
   - **Redirect URL**: `https://your-domain.com/slack/oauth/callback`

4. Add Slash Command:
   - **Command**: `/reddit`
   - **Request URL**: `https://your-domain.com/api/slack/command`
   - **Description**: Search Reddit with AI-powered analytics

### 2. Environment Variables

Set these environment variables in your deployment:

```bash
# Slack App Configuration
SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret
SLACK_SIGNING_SECRET=your_slack_signing_secret

# Reddit API (Optional - will show demo data if not set)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=RedditScraperPro/1.0

# Security
SECRET_KEY=your_secret_encryption_key
ADMIN_KEY=your_admin_dashboard_key

# Database
DATABASE_PATH=/app/data/scraper.db
```

### 3. Database Setup

The app will automatically create the SQLite database on first run with these tables:
- `workspaces` - Store workspace info and encrypted tokens
- `workspace_users` - Track users in each workspace
- `usage_logs` - Command usage analytics
- `installations` - Installation history

### 4. Deploy Application

#### Vercel Deployment (Recommended)
```bash
# Deploy to Vercel
vercel --prod

# Set environment variables
vercel env add SLACK_CLIENT_ID
vercel env add SLACK_CLIENT_SECRET
# ... add all other env vars
```

#### Heroku Deployment
```bash
# Create Heroku app
heroku create reddit-scraper-pro

# Set environment variables
heroku config:set SLACK_CLIENT_ID=your_client_id
heroku config:set SLACK_CLIENT_SECRET=your_secret
# ... add all other env vars

# Deploy
git push heroku main
```

#### Docker Deployment
```bash
# Build image
docker build -t reddit-scraper-pro .

# Run container
docker run -d \
  -p 5000:5000 \
  -e SLACK_CLIENT_ID=your_client_id \
  -e SLACK_CLIENT_SECRET=your_secret \
  -v /data/scraper:/app/data \
  reddit-scraper-pro
```

### 5. Slack App Distribution

1. **Development**: Test with your workspace first
2. **Public Distribution**: Submit app to Slack App Directory
3. **Custom Installation**: Share installation URL: `https://your-domain.com/slack/install`

## 📊 Admin Features

### Admin Dashboard
Access: `https://your-domain.com/admin/workspaces?key=your_admin_key`

Features:
- View all connected workspaces
- Monitor usage statistics
- Activate/deactivate workspaces
- Reset usage counts
- View detailed logs

### Billing Dashboard
Access: `https://your-domain.com/admin/billing?key=your_admin_key`

Features:
- Revenue analytics
- Plan distribution
- Usage metrics
- Top customers

### Workspace Management
- **Activate/Deactivate**: Control workspace access
- **Usage Reset**: Reset monthly usage counts
- **View Logs**: Detailed usage history per workspace

## 🎛️ Usage Plans

### Free Tier
- 100 searches/month
- Basic functionality
- Community support

### Pro Tier ($29/month)
- 1,000 searches/month
- Advanced features
- Priority support

### Enterprise ($99/month)
- 10,000 searches/month
- Custom features
- 24/7 support

## 🔒 Security Features

- **Token Encryption**: All Slack tokens encrypted with Fernet
- **Rate Limiting**: 10 commands/hour per user
- **Admin Authentication**: Secure admin access
- **HTTPS Only**: All communications encrypted
- **No Token Logging**: Sensitive data never logged

## 🧪 Testing

### Test Installation
1. Visit: `https://your-domain.com/slack/install`
2. Install to your test workspace
3. Try commands: `/reddit help`, `/reddit search AI`

### Admin Testing
1. Check workspace appears in dashboard
2. Monitor usage counts
3. Test admin controls

### Rate Limit Testing
1. Execute 10+ commands within an hour
2. Verify rate limiting activates
3. Check error messages

## 📝 Commands

### Basic Commands
- `/reddit help` - Show help
- `/reddit status` - System status
- `/reddit search [keywords]` - Search Reddit

### Advanced Search
- `/reddit search AI in technology` - Search specific subreddit
- `/reddit search crypto top 50` - Limit results
- `/reddit search startups hot` - Sort by hot

## 🔧 Troubleshooting

### Common Issues

1. **Installation Failed**
   - Check Slack app credentials
   - Verify redirect URL
   - Check network connectivity

2. **Commands Not Working**
   - Verify slash command URL
   - Check app scopes
   - Review error logs

3. **Database Issues**
   - Check database path permissions
   - Verify SQLite is available
   - Review database logs

### Log Files
- Application logs show all operations
- Admin dashboard shows usage patterns
- Individual workspace logs available

## 🚀 Scaling

### High Traffic
- Use PostgreSQL instead of SQLite
- Add Redis for caching
- Implement horizontal scaling

### Multiple Regions
- Deploy to multiple regions
- Use CDN for static assets
- Database replication

## 📞 Support

- **Installation Help**: Check deployment logs
- **Usage Questions**: `/reddit help` command
- **Enterprise Support**: Contact sales team
- **Technical Issues**: Review admin dashboard

## 🎉 Success!

Your Reddit Scraper Pro is now a universal Slack app supporting:
- ✅ Multi-tenant architecture
- ✅ Secure OAuth installation
- ✅ Encrypted token storage
- ✅ Usage tracking & billing
- ✅ Admin management tools
- ✅ Rate limiting & security
- ✅ Scalable deployment

Users can now install your app to their workspaces and use `/reddit` commands with their own secure tokens and usage limits!