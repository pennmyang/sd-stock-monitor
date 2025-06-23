import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
import json
from datetime import datetime

def send_notification(subject, message):
    """Send email notification using environment variables"""
    try:
        sender_email = os.environ.get('SENDER_EMAIL')
        sender_password = os.environ.get('SENDER_PASSWORD')
        recipient_email = os.environ.get('RECIPIENT_EMAIL')
        
        if not all([sender_email, sender_password, recipient_email]):
            print("Email credentials not configured")
            return False
            
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

def check_stock_status(url):
    """Check if any Steam Deck models are in stock on the listing page"""
    try:
        # Headers specifically designed to get desktop version and avoid mobile redirect
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            # Force desktop version
            'Sec-CH-UA': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-CH-UA-Mobile': '?0',  # Important: Tell Steam we're NOT mobile
            'Sec-CH-UA-Platform': '"Windows"',
            'Viewport-Width': '1920'  # Desktop viewport
        }
        
        # Use session with cookies to maintain state
        session = requests.Session()
        session.headers.update(headers)
        
        # First, try to get the desktop version directly
        desktop_url = url
        if '?' in desktop_url:
            desktop_url += '&desktop=1'
        else:
            desktop_url += '?desktop=1'
            
        print(f"🔍 Requesting desktop version: {desktop_url}")
        
        response = session.get(desktop_url, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text().lower()
        
        print(f"🔍 Page title: {soup.title.string if soup.title else 'No title found'}")
        print(f"📄 Response status: {response.status_code}")
        print(f"📄 Final URL: {response.url}")
        print(f"📄 Content length: {len(response.content)} bytes")
        print(f"📄 Page text length: {len(page_text)} characters")
        
        # Check if we got mobile version (bad signs)
        mobile_indicators = [
            'get the steam mobile app',
            'view desktop website',
            'mobile version',
            'switch to desktop'
        ]
        
        mobile_detected = any(indicator in page_text for indicator in mobile_indicators)
        print(f"🔍 Mobile version detected: {mobile_detected}")
        
        # Check for desktop/product page indicators (good signs)
        desktop_indicators = [
            'steam deck',
            'certified refurbished',
            'valve',
            '£389',
            '£459',
            'out of stock',
            'add to cart'
        ]
        
        desktop_content_score = sum(1 for indicator in desktop_indicators if indicator in page_text)
        print(f"🔍 Desktop content indicators found: {desktop_content_score}/{len(desktop_indicators)}")
        
        # If we got mobile version, show sample and exit
        if mobile_detected or desktop_content_score < 3:
            print("❌ Got mobile version or insufficient content")
            sample_text = page_text[:1500] if len(page_text) > 1500 else page_text
            print(f"🔍 Page sample (first 1500 chars): {sample_text}")
            return "ERROR"
        
        # Now look for stock indicators (we have desktop version)
        out_of_stock_variations = [
            'out of stock',
            'outofstock', 
            'sold out',
            'soldout',
            'unavailable',
            'not available',
            'coming soon'
        ]
        
        in_stock_variations = [
            'add to cart',
            'buy now',
            'purchase',
            'order now',
            'buy',
            'order',
            'available now'
        ]
        
        # Count stock indicators
        out_of_stock_count = sum(page_text.count(phrase) for phrase in out_of_stock_variations)
        in_stock_count = sum(page_text.count(phrase) for phrase in in_stock_variations)
        
        print(f"🔍 Stock analysis:")
        print(f"   - Out of stock mentions: {out_of_stock_count}")
        print(f"   - In stock mentions: {in_stock_count}")
        
        # Look for Steam Deck models
        model_counts = {
            '512 gb oled': page_text.count('512 gb oled') + page_text.count('512gb oled'),
            '1tb oled': page_text.count('1tb oled') + page_text.count('1 tb oled'),
            '64 gb lcd': page_text.count('64 gb lcd') + page_text.count('64gb lcd'),
            '256 gb lcd': page_text.count('256 gb lcd') + page_text.count('256gb lcd'),
            '512 gb lcd': page_text.count('512 gb lcd') + page_text.count('512gb lcd')
        }
        
        total_models = sum(count for count in model_counts.values() if count > 0)
        print(f"🔍 Steam Deck models detected: {total_models}")
        for model, count in model_counts.items():
            if count > 0:
                print(f"   - {model}: {count}")
        
        # Check for prices to confirm we have product listings
        price_mentions = sum(page_text.count(price) for price in ['£389', '£459', '£249', '£279', '£319'])
        print(f"🔍 Price mentions: {price_mentions}")
        
        # Decision logic
        if out_of_stock_count >= 3 and total_models >= 2:
            print(f"✅ Confirmed: {out_of_stock_count} out-of-stock mentions for {total_models} models")
            return "OUT_OF_STOCK"
        elif in_stock_count > 0 and out_of_stock_count == 0 and total_models >= 2:
            print(f"✅ Confirmed: {in_stock_count} in-stock mentions, no out-of-stock")
            return "IN_STOCK"
        elif in_stock_count > 0 and out_of_stock_count > 0 and total_models >= 2:
            print(f"✅ Mixed stock: {in_stock_count} available, {out_of_stock_count} unavailable")
            return "PARTIAL_STOCK"
        else:
            print("❓ Insufficient data to determine stock status")
            # Show more context for debugging
            sample_text = page_text[:2000] if len(page_text) > 2000 else page_text
            print(f"🔍 Extended sample: {sample_text}")
            return "UNKNOWN"
            
    except requests.RequestException as e:
        print(f"❌ Error fetching webpage: {e}")
        return "ERROR"
    except Exception as e:
        print(f"❌ Error parsing webpage: {e}")
        return "ERROR"

def load_previous_status():
    """Load the previous status from GitHub environment or return None"""
    try:
        # In GitHub Actions, we can use a file to store state between runs
        if os.path.exists('last_status.json'):
            with open('last_status.json', 'r') as f:
                data = json.load(f)
                return data.get('status'), data.get('timestamp')
    except:
        pass
    return None, None

def save_current_status(status):
    """Save current status for next run"""
    try:
        data = {
            'status': status,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        with open('last_status.json', 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Warning: Could not save status: {e}")

def main():
    """Main monitoring function"""
    url = os.environ.get('MONITOR_URL')
    if not url:
        print("❌ MONITOR_URL environment variable not set")
        sys.exit(1)
    
    print(f"🔍 Checking stock status for: {url}")
    print(f"⏰ Check time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Load previous status
    previous_status, last_check = load_previous_status()
    print(f"📝 Previous status: {previous_status} (last checked: {last_check})")
    
    # Check current status
    current_status = check_stock_status(url)
    print(f"📊 Current status: {current_status}")
    
    # Only send notification if status changed from OUT_OF_STOCK/UNKNOWN to IN_STOCK or PARTIAL_STOCK
    if (current_status in ["IN_STOCK", "PARTIAL_STOCK"]) and previous_status not in ["IN_STOCK", "PARTIAL_STOCK"]:
        if current_status == "IN_STOCK":
            subject = "🎉 STEAM DECK ALERT - All Models in Stock!"
            status_message = "All Steam Deck models appear to be in stock!"
        else:  # PARTIAL_STOCK
            subject = "🎉 STEAM DECK ALERT - Some Models Available!"
            status_message = "Some Steam Deck models appear to be back in stock!"
            
        message = f"""
🎉 GREAT NEWS! 🎉

{status_message}

URL: {url}
Previous status: {previous_status or 'Unknown'}
Current status: {current_status}
Check time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

Go check which models are available! 🏃‍♂️💨

Steam Deck models to look for:
- Steam Deck 512 GB OLED (£389.00)
- Steam Deck 1TB OLED (£459.00)

This alert was sent by your GitHub Actions stock monitor.
Only sent when status changes to indicate availability.
        """
        print(f"🎉 STATUS CHANGED: STEAM DECK(S) NOW AVAILABLE! Sending notification...")
        send_notification(subject, message)
        
    elif current_status in ["IN_STOCK", "PARTIAL_STOCK"] and previous_status in ["IN_STOCK", "PARTIAL_STOCK"]:
        print("✅ Steam Deck(s) still available (no notification sent - status unchanged)")
        
    elif current_status == "OUT_OF_STOCK":
        if previous_status in ["IN_STOCK", "PARTIAL_STOCK"]:
            print("📦 Steam Deck went from available to out-of-stock")
        else:
            print("📦 All Steam Deck models are still out of stock")
            
    elif current_status == "UNKNOWN":
        print("❓ Could not determine Steam Deck stock status")
        
    else:  # ERROR
        print("⚠️ Error occurred while checking")
    
    # Save current status for next run
    save_current_status(current_status)

if __name__ == "__main__":
    main() 