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
    """Check if any Steam Deck models are in stock - simplified approach"""
    try:
        # Minimal headers to avoid triggering bot detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        print(f"🔍 Attempting to fetch Steam page...")
        
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        # Get both HTML content and raw text
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text().lower()
        html_content = str(soup).lower()
        
        print(f"🔍 Page title: {soup.title.string if soup.title else 'No title found'}")
        print(f"📄 Response status: {response.status_code}")
        print(f"📄 Content length: {len(response.content)} bytes")
        print(f"📄 Page text length: {len(page_text)} characters")
        
        # Basic verification that we're on a Steam page
        steam_indicators = [
            'steam' in page_text,
            'valve' in page_text or 'valve' in html_content,
            len(page_text) > 1000  # Minimum content length
        ]
        
        if not any(steam_indicators):
            print("❌ Not a valid Steam page or insufficient content")
            return "ERROR"
        
        print("✅ Confirmed we're on a Steam page")
        
        # Look for ANY indication this is the Steam Deck page
        deck_indicators = [
            'deck' in page_text,
            'refurbished' in page_text,
            'certified' in page_text
        ]
        
        deck_mentions = sum(1 for indicator in deck_indicators if indicator)
        print(f"🔍 Steam Deck page indicators: {deck_mentions}/3")
        
        if deck_mentions < 2:
            print("⚠️ This doesn't appear to be the Steam Deck page")
            # Still try to detect stock status in case we're on a different version
        
        # Simple stock detection - look for key phrases anywhere in the content
        # Check both visible text and HTML (in case text is in attributes, etc.)
        # Binary approach: Just look for "Out of stock" vs anything else
        combined_content = page_text + " " + html_content
        
        # Count Steam's exact "Out of stock" phrase
        out_of_stock_count = combined_content.count('out of stock')
        
        print(f"🔍 Binary stock detection:")
        print(f"   - 'Out of stock' mentions: {out_of_stock_count}")
        
        # Verify we're on the Steam Deck page (basic sanity check)
        steam_deck_mentions = combined_content.count('steam deck')
        refurbished_mentions = combined_content.count('refurbished')
        
        print(f"🔍 Page verification:")
        print(f"   - Steam Deck page confirmed: {steam_deck_mentions > 0 and refurbished_mentions > 0}")
        
        if steam_deck_mentions == 0 or refurbished_mentions == 0:
            print("❌ Not the Steam Deck refurbished page")
            return "ERROR"
        
        # Binary decision: Either all out of stock, or something is available
        if out_of_stock_count >= 5:
            print(f"📦 All models out of stock ({out_of_stock_count} instances)")
            return "OUT_OF_STOCK"
        elif out_of_stock_count > 0:
            print(f"🎉 Some models may be available! (only {out_of_stock_count} showing 'out of stock')")
            return "IN_STOCK"  # If fewer than 5 are out of stock, something must be available
        else:
            print(f"🎉 No 'out of stock' found - models likely available!")
            return "IN_STOCK"
            
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