# Cookie Issues in Hugging Face Spaces

If you're having trouble staying logged in on Hugging Face Spaces, particularly on mobile devices, try these solutions:

## For iPhone/iPad Users

1. Go to Settings > Safari > Privacy & Security
2. Make sure "Block All Cookies" is turned OFF
3. Ensure "Prevent Cross-Site Tracking" is turned OFF (this can block cookies in iframes)
4. Try opening the app in Safari directly, not within another app's browser view

## For Android Users

1. Go to Settings > Privacy > Cookies
2. Make sure cookies are allowed
3. Consider disabling tracking prevention features

## General Solutions

1. Try opening the app in a regular browser tab instead of an iframe
2. Clear your browser cookies and cache
3. Try a different browser
4. If using the app in "Private" or "Incognito" mode, try regular browsing mode instead

## Why This Happens

Hugging Face Spaces runs apps in iframes, which can trigger strict cookie policies in modern browsers, especially on mobile devices. This is a security feature of browsers, but it can interfere with web applications that need to maintain login sessions.