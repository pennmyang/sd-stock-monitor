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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print(f"🔍 Page title: {soup.title.string if soup.title else 'No title found'}")
        print(f"📄 Checking Steam Deck listing page...")
        
        # Look for Steam Deck product sections
        # Steam pages often use specific classes or data attributes
        steam_deck_sections = []
        
        # Try to find product containers - Steam uses various class names
        possible_containers = [
            soup.find_all(class_=lambda x: x and 'item' in x.lower()),
            soup.find_all(class_=lambda x: x and 'product' in x.lower()),
            soup.find_all(class_=lambda x: x and 'game' in x.lower()),
            soup.find_all('div', string=lambda text: text and 'steam deck' in text.lower()),
            # Look for any div containing "Steam Deck" text
            [div.parent for div in soup.find_all(string=lambda text: text and 'steam deck' in text.lower()) if div.parent]
        ]
        
        # Flatten the list and remove duplicates
        all_containers = []
        for container_list in possible_containers:
            all_containers.extend(container_list)
        
        # Remove duplicates
        unique_containers = list(set(all_containers))
        
        print(f"🔍 Found {len(unique_containers)} potential product containers")
        
        # Look for stock status indicators
        in_stock_models = []
        out_of_stock_models = []
        
        # Check the entire page text for stock indicators
        page_text = soup.get_text().lower()
        
        # Count occurrences of stock indicators
        out_of_stock_count = page_text.count('out of stock')
        sold_out_count = page_text.count('sold out')
        unavailable_count = page_text.count('unavailable')
        
        # Look for purchase-related text
        add_to_cart_count = page_text.count('add to cart')
        buy_now_count = page_text.count('buy now')
        purchase_count = page_text.count('purchase')
        
        print(f"🔍 Stock indicators found:")
        print(f"   - 'out of stock': {out_of_stock_count}")
        print(f"   - 'sold out': {sold_out_count}")
        print(f"   - 'unavailable': {unavailable_count}")
        print(f"   - 'add to cart': {add_to_cart_count}")
        print(f"   - 'buy now': {buy_now_count}")
        print(f"   - 'purchase': {purchase_count}")
        
        # Look for specific Steam Deck models mentioned in your image
        steam_deck_512_mentions = page_text.count('512 gb')
        steam_deck_1tb_mentions = page_text.count('1tb')
        
        print(f"🔍 Steam Deck models found:")
        print(f"   - 512 GB mentions: {steam_deck_512_mentions}")
        print(f"   - 1TB mentions: {steam_deck_1tb_mentions}")
        
        # Try to find any buttons that might indicate stock status
        buttons = soup.find_all(['button', 'input', 'a'])
        button_texts = [btn.get_text().strip().lower() for btn in buttons if btn.get_text()]
        purchase_buttons = [text for text in button_texts if any(word in text for word in ['buy', 'purchase', 'cart', 'order'])]
        
        print(f"🔍 Found {len(buttons)} buttons total, {len(purchase_buttons)} purchase-related")
        if purchase_buttons:
            print(f"   Purchase button examples: {purchase_buttons[:3]}")
        
        # Decision logic for Steam Deck listing page
        total_out_of_stock = out_of_stock_count + sold_out_count + unavailable_count
        total_purchase_options = add_to_cart_count + buy_now_count + purchase_count
        
        if total_purchase_options > 0 and total_out_of_stock == 0:
            return "IN_STOCK"
        elif total_out_of_stock > 0 and total_purchase_options == 0:
            return "OUT_OF_STOCK"
        elif total_out_of_stock > 0 and total_purchase_options > 0:
            # Mixed state - some in stock, some out of stock
            print(f"🔍 Mixed stock status detected - some items may be available")
            return "PARTIAL_STOCK"
        else:
            # Show some sample text to help debug
            sample_text = page_text[:800] if len(page_text) > 800 else page_text
            print(f"🔍 Sample page text (first 800 chars): {sample_text}")
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