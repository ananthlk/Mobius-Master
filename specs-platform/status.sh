#!/bin/bash
# Specs Catalog Status Check
# Run this anytime to see deployment status and understand what's happening

PROJECT="mobius-os-dev"
SERVICE="mobius-specs"
REGION="us-central1"

echo "🔍 Mobius Specs Catalog Status"
echo "=================================="
echo ""

# 1. Service status
echo "📍 Service Status:"
STATUS=$(gcloud run describe $SERVICE --region=$REGION --project=$PROJECT --format='value(status.observedGeneration,status.address.url)')
URL=$(echo "$STATUS" | tail -1)
echo "   URL: $URL"
echo ""

# 2. Latest deployment
echo "🚀 Latest Deployment:"
LATEST=$(gcloud run revisions list --service=$SERVICE --region=$REGION --project=$PROJECT --limit=1 --format='value(metadata.name,metadata.creationTimestamp,spec.containers[0].image)')
REV_NAME=$(echo "$LATEST" | awk '{print $1}')
REV_DATE=$(echo "$LATEST" | awk '{print $2}')
REV_IMAGE=$(echo "$LATEST" | awk '{print $3}')

echo "   Revision: $REV_NAME"
echo "   Deployed: $REV_DATE"
echo "   Image: $REV_IMAGE"
echo ""

# 3. Recent commits (what triggered the build)
echo "📝 Recent Commits (what you pushed):"
git log --oneline -3 | sed 's/^/   /'
echo ""

# 4. Build status
echo "🔨 Build Status:"
BUILDS=$(gcloud builds list --filter="name:$SERVICE" --limit=3 --project=$PROJECT --format='value(id,status,createTime)')
if [ -z "$BUILDS" ]; then
    echo "   No builds found"
else
    echo "$BUILDS" | while read BUILD; do
        BUILD_ID=$(echo "$BUILD" | awk '{print $1}' | cut -c1-8)
        BUILD_STATUS=$(echo "$BUILD" | awk '{print $2}')
        BUILD_DATE=$(echo "$BUILD" | awk '{print $3}')
        STATUS_EMOJI="❓"
        [ "$BUILD_STATUS" = "SUCCESS" ] && STATUS_EMOJI="✅"
        [ "$BUILD_STATUS" = "FAILURE" ] && STATUS_EMOJI="❌"
        [ "$BUILD_STATUS" = "QUEUED" ] && STATUS_EMOJI="⏳"
        [ "$BUILD_STATUS" = "WORKING" ] && STATUS_EMOJI="🔨"

        echo "   $STATUS_EMOJI $BUILD_ID: $BUILD_STATUS ($BUILD_DATE)"
    done
fi
echo ""

# 5. Health check
echo "💚 Health Check:"
if curl -s -o /dev/null -w "%{http_code}" "$URL" | grep -q "200"; then
    echo "   ✅ Site is responding (HTTP 200)"
else
    echo "   ❌ Site may be down (not responding)"
fi
echo ""

# 6. How to understand the output
echo "📖 How to Read This:"
echo "   ✅ SUCCESS = deployment completed, site is live"
echo "   🔨 WORKING = build in progress, site might be redeploying"
echo "   ⏳ QUEUED = build waiting to start"
echo "   ❌ FAILURE = build failed (check 'gcloud builds log <id>')"
echo ""

# 7. What to do if something looks wrong
echo "🆘 If Something Looks Wrong:"
echo "   • Site down? Usually redeploys in 2 minutes after you push"
echo "   • Build failed? Run: gcloud builds log <BUILD_ID>"
echo "   • Specs stale? Check git log to see if your push succeeded"
echo ""

echo "=================================="
echo "✨ Specs Catalog is auto-maintained by git"
echo "   Just git push → site redeploys in ~2 minutes"
