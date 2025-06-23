import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
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
    """Check if item is in stock"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text().lower()
        
        # Look for out of stock indicators
        out_of_stock_phrases = [
            "out of stock",
            "sold out", 
            "unavailable",
            "not available",
            "coming soon"
        ]
        
        # Look for in stock indicators
        in_stock_phrases = [
            "add to cart",
            "buy now",
            "purchase",
            "add to basket",
            "order now",
            "in stock"
        ]
        
        has_out_of_stock = any(phrase in page_text for phrase in out_of_stock_phrases)
        has_in_stock = any(phrase in page_text for phrase in in_stock_phrases)
        
        # Check for purchase buttons
        purchase_buttons = soup.find_all(['button', 'input', 'a'], 
                                       string=lambda text: text and any(word in text.lower() 
                                       for word in ['buy', 'purchase', 'add to cart', 'order']))
        
        enabled_buttons = [btn for btn in purchase_buttons if not btn.get('disabled')]
        
        if has_in_stock and enabled_buttons and not has_out_of_stock:
            return "IN_STOCK"
        elif has_out_of_stock:
            return "OUT_OF_STOCK"
        else:
            return "UNKNOWN"
            
    except requests.RequestException as e:
        print(f"❌ Error fetching webpage: {e}")
        return "ERROR"
    except Exception as e:
        print(f"❌ Error parsing webpage: {e}")
        return "ERROR"

def main():
    """Main monitoring function"""
    url = os.environ.get('MONITOR_URL')
    if not url:
        print("❌ MONITOR_URL environment variable not set")
        sys.exit(1)
    
    print(f"🔍 Checking stock status for: {url}")
    print(f"⏰ Check time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    status = check_stock_status(url)
    
    if status == "IN_STOCK":
        subject = "🎉 STOCK ALERT - Item Available!"
        message = f"""
Great news! The item you're monitoring appears to be back in stock!

URL: {url}
Check time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

Go grab it now! 🏃‍♂️💨

This alert was sent by your GitHub Actions stock monitor.
        """
        print("🎉 ITEM APPEARS TO BE IN STOCK!")
        send_notification(subject, message)
        
    elif status == "OUT_OF_STOCK":
        print("📦 Item is out of stock")
        
    elif status == "UNKNOWN":
        print("❓ Could not determine stock status")
        
    else:  # ERROR
        print("⚠️ Error occurred while checking")

if __name__ == "__main__":
    main() 