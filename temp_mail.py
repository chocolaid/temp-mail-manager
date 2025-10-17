import requests
import time
import json
import re

class TempMail:
    def __init__(self):
        self.base_url = "https://temp-mail-manager.fly.dev"
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }
        self.session_id = None
        self.email = None
        self.inbox = []

    def create_email(self):
        """Create a new temporary email address"""
        response = requests.get(f"{self.base_url}/create-email", headers=self.headers)
        if response.ok:
            data = response.json()
            self.session_id = data.get("sessionId")
            self.email = data.get("email")
            return self.email
        else:
            raise Exception(f"Failed to create email: {response.text}")

    def get_inbox(self):
        """Get all messages in the inbox"""
        if not self.session_id:
            raise Exception("Session not created yet")
        
        response = requests.get(
            f"{self.base_url}/get-inbox/{self.session_id}",
            headers=self.headers
        )
        
        if response.ok:
            data = response.json()
            self.inbox = data.get("inbox", [])
            return self.inbox
        else:
            return []

    def wait_for_message(self, subject_keyword="", timeout=60, check_interval=5, verbose=False):
        """Wait for a message with specific subject keyword"""
        if not self.session_id:
            raise Exception("Session not created yet")
            
        elapsed = 0
        while elapsed < timeout:
            if verbose:
                print(f"Checking inbox at {elapsed}s...")
            messages = self.get_inbox()
            for msg in messages:
                subject = msg.get("subject", "")
                if isinstance(subject, str) and subject_keyword.lower() in subject.lower():
                    if verbose:
                        print("Match found!")
                    return msg
            time.sleep(check_interval)
            elapsed += check_interval
        if verbose:
            print("Timeout reached, no matching message.")
        return None

    def get_message_by_subject(self, keyword):
        """Get a specific message by subject keyword"""
        if not self.inbox:
            self.get_inbox()
        for msg in self.inbox:
            subject = msg.get("subject", "")
            if isinstance(subject, str) and keyword.lower() in subject.lower():
                return msg
        return None

    def extract_links(self, message=None):
        """Extract links from an email message"""
        if message is None:
            if not self.inbox:
                self.get_inbox()
            if not self.inbox:
                return []
            message = self.inbox[0]
        
        # Extract links from the message body
        body = message.get("snippet", "")
        return re.findall(r'https?://[^\s<>"\']+', body)

    def kill_session(self):
        """Close the current session"""
        if not self.session_id:
            return True
            
        response = requests.get(
            f"{self.base_url}/kill-session/{self.session_id}",
            headers=self.headers
        )
        
        if response.ok:
            self.session_id = None
            self.email = None
            self.inbox = []
            return True
        return False

    def to_json(self, filepath="inbox.json"):
        """Save inbox to JSON file"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.inbox, f, indent=2)
        return filepath

    def __str__(self):
        return f"TempMail({self.email}) with {len(self.inbox)} messages"

    def latest_subjects(self, limit=5):
        """Get latest email subjects"""
        self.get_inbox()
        return [msg.get("subject") for msg in self.inbox[:limit]]

    def test_parsing(self, json_file="example_inbox.json"):
        """Test parsing Pinterest verification emails from a JSON file
        
        Args:
            json_file (str): Path to JSON file containing example inbox data
            
        Returns:
            dict: Results of parsing test
        """
        try:
            # Load the example data
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            results = {
                "success": False,
                "messages_found": len(data),
                "pinterest_emails": 0,
                "verification_links": []
            }
            
            # Test parsing each message
            for message in data:
                if 'from' in message and 'pinterest' in message.get('from', '').lower():
                    results['pinterest_emails'] += 1
                    
                    # Extract links
                    links = self.extract_links(message)
                    
                    # If standard method fails, try a targeted approach for this example
                    if not links:
                        body_text = message.get('body_text', '')
                        
                        # Try to find specific patterns in the Pinterest email
                        targets = re.findall(r'target=([^&\s]+)', body_text)
                        for target in targets:
                            try:
                                import urllib.parse
                                decoded = urllib.parse.unquote(target)
                                # Look for autologin with next=verify
                                if 'autologin' in decoded and 'next=' in decoded and 'verify' in decoded:
                                    links.append(decoded)
                            except:
                                pass
                    
                    # Debug the found links
                    verification_links = []
                    for url in links:
                        link_info = {"url": url}
                        
                        # Categorize the link
                        if '/verify' in url:
                            link_info["type"] = "direct"
                        elif '/autologin/' in url and 'next=' in url:
                            link_info["type"] = "autologin"
                        elif 'pinterest.com' in url:
                            link_info["type"] = "pinterest"
                        else:
                            link_info["type"] = "other"
                            
                        verification_links.append(link_info)
                    
                    results['verification_links'].extend(verification_links)
            
            # Try a more specific approach if no verification links found
            if not results['verification_links'] and results['pinterest_emails'] > 0:
                for message in data:
                    if 'from' in message and 'pinterest' in message.get('from', '').lower():
                        body_text = message.get('body_text', '')
                        # Look for the URL with verify code parameter
                        verify_urls = re.findall(r'(https://www\.pinterest\.com/[^\s]*?verify[^\s]*)', body_text)
                        for url in verify_urls:
                            results['verification_links'].append({
                                "type": "direct",
                                "url": url
                            })
                        
                        # Also try to find autologin URLs that contain verify
                        autologin_urls = re.findall(r'(https://www\.pinterest\.com/secure/autologin/[^\s]*)', body_text)
                        for url in autologin_urls:
                            results['verification_links'].append({
                                "type": "autologin",
                                "url": url
                            })
            
            results['success'] = len(results['verification_links']) > 0
            
            return results
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

def debug_example_inbox():
    """Debug function to analyze example_inbox.json in detail"""
    print("Analyzing example_inbox.json in detail...")
    
    try:
        with open("example_inbox.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"Found {len(data)} messages in example_inbox.json")
        
        for i, message in enumerate(data):
            print(f"\nMessage {i+1}:")
            print(f"  From: {message.get('from', 'N/A')}")
            print(f"  Subject: {message.get('subject', 'N/A')}")
            
            # Find verification info
            body_text = message.get('body_text', '')
            
            # Find code and uid
            verify_codes = re.findall(r'code=([a-f0-9]{32})', body_text)
            uid_matches = re.findall(r'uid=(\d+)', body_text)
            
            if verify_codes:
                print(f"  Verification code: {verify_codes[0]}")
            if uid_matches:
                print(f"  User ID: {uid_matches[0]}")
            
            # Look for autologin URLs
            autologin_urls = re.findall(r'(https://www\.pinterest\.com/secure/autologin/[^\s"\'<>]+)', body_text)
            if autologin_urls:
                print(f"  Found {len(autologin_urls)} autologin URLs")
                for url in autologin_urls[:1]:  # Show just the first one
                    print(f"  Sample autologin URL: {url[:100]}...")
            
            # Look for target parameters
            target_matches = re.findall(r'target=(https?%3A%2F%2F[^&\s]+)', body_text)
            if target_matches:
                print(f"  Found {len(target_matches)} target parameters")
                
                for target in target_matches[:1]:  # Show just the first one
                    try:
                        import urllib.parse
                        decoded = urllib.parse.unquote(target)
                        print(f"  Decoded target: {decoded[:100]}...")
                        
                        # Check for verification in the decoded target
                        if 'verify' in decoded:
                            print("  ✓ Target contains 'verify'")
                        if 'autologin' in decoded:
                            print("  ✓ Target contains 'autologin'")
                        if 'next=' in decoded:
                            print("  ✓ Target contains 'next='")
                    except Exception as e:
                        print(f"  Error decoding target: {str(e)}")

    except Exception as e:
        print(f"Error analyzing example_inbox.json: {str(e)}")

# Example usage
if __name__ == "__main__":
    temp_mail = TempMail()
    
    try:
        # Create a new email
        email = temp_mail.create_email()
        print(f"Generated email: {email}")
        
        # Wait for messages
        print("Waiting for messages...")
        message = temp_mail.wait_for_message(timeout=60, verbose=True)
        
        if message:
            print(f"Received message: {message.get('subject')}")
            links = temp_mail.extract_links(message)
            print(f"Found links: {links}")
        else:
            print("No messages received.")
            
        # Kill the session when done
        temp_mail.kill_session()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        # Make sure to kill the session even if there's an error
        temp_mail.kill_session()
