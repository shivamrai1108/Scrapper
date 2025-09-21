# 🔧 SLACK APP SETUP INSTRUCTIONS

## 🚨 **Current Issue**: Invalid client_id parameter

Your Slack OAuth is failing because we need to set up real Slack app credentials. Here's the step-by-step fix:

## 📋 **Step-by-Step Setup**

### **1. Create Slack App (5 minutes)**

1. **Visit**: https://api.slack.com/apps
2. **Click**: "Create New App" → "From scratch"
3. **Fill**:
   - **App Name**: `Reddit Scraper Pro`
   - **Workspace**: Choose your workspace (for development)

### **2. Configure OAuth & Permissions**

1. **Go to**: "OAuth & Permissions" in left sidebar
2. **Add Redirect URLs**:
   ```
   https://scrapper-eight-alpha.vercel.app/slack/oauth/callback
   ```
3. **Add Bot Token Scopes**:
   ```
   commands
   chat:write
   users:read
   channels:read
   groups:read
   ```

### **3. Add Slash Command**

1. **Go to**: "Slash Commands" in left sidebar
2. **Click**: "Create New Command"
3. **Fill**:
   - **Command**: `/reddit`
   - **Request URL**: `https://scrapper-eight-alpha.vercel.app/api/slack/command`
   - **Short Description**: `Search Reddit with AI-powered analytics`
   - **Usage Hint**: `search [keywords]`

### **4. Get Your Credentials**

1. **Go to**: "Basic Information" in left sidebar
2. **Copy**:
   - **Client ID** (numbers like: `1234567890.1234567890`)
   - **Client Secret** (click "Show" to reveal)

### **5. Set Environment Variables**

Run these commands with YOUR actual values:

```bash
cd /Users/shivamrai/Scrapper-Fresh

# Add Slack Client ID
echo "YOUR_CLIENT_ID_HERE" | vercel env add SLACK_CLIENT_ID production

# Add Slack Client Secret  
echo "YOUR_CLIENT_SECRET_HERE" | vercel env add SLACK_CLIENT_SECRET production

# Redeploy with new environment variables
vercel --prod
```

### **6. Test Installation**

1. **Visit**: https://scrapper-eight-alpha.vercel.app/slack/install
2. **Click**: "Install to Slack" 
3. **Authorize**: The app in your workspace
4. **Test**: Use `/reddit help` in any Slack channel

## 🔍 **Example Values**

**Client ID**: `1234567890.1234567890`  
**Client Secret**: `abcd1234efgh5678ijkl9012mnop3456`  
**Redirect URL**: `https://scrapper-eight-alpha.vercel.app/slack/oauth/callback`  
**Slash Command URL**: `https://scrapper-eight-alpha.vercel.app/api/slack/command`  

## 🎯 **After Setup**

Once configured, customers can:
1. Visit: https://scrapper-eight-alpha.vercel.app/slack/install
2. Install with one click (no more errors!)
3. Use `/reddit search AI startups` immediately
4. Get billed automatically based on usage

## ⚡ **Quick Commands Reference**

```bash
# Check current environment variables
vercel env ls

# Add new environment variable
echo "value" | vercel env add VARIABLE_NAME production

# Redeploy with new variables
vercel --prod

# Test the installation
curl https://scrapper-eight-alpha.vercel.app/slack/install
```

## 🎊 **Success!**

After completing these steps, your universal Slack app will be fully functional and ready to serve thousands of customers!

---

**Need help?** The setup should take about 5-10 minutes total. Once done, your SaaS platform will be complete and ready for customer acquisition!