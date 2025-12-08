import requests
from ..config.config_manager import settings, save_settings

def send_discord_alert_webhook(chamber: int | str, new_status: str) -> bool:
    """
    Sends a message to a Discord webhook URL.

    Parameters:
        chamber (`int`): 
            The chamber slot number
        new_status: (`str`): 
            The new status of the chamber

    Returns:
        `bool`: True if the message was sent successfully, False otherwise.
    """
    wh = settings.get("discord_alert_webhook", False)
    if not wh: return False

    payload = {
        "content": f"Chamber {chamber} {new_status}"
    }
    try:
        if (settings.get("DEBUG", False)): print(f'Sending "{payload["content"]}" to webhook {wh}')
        response = requests.post(wh, json=payload)
        return response.status_code == 204  # Discord returns 204 No Content on success
    except requests.exceptions.RequestException as e:
        print(f"Error sending webhook: {e}")
        return False
    
    
if __name__ == "__main__":
    chamber = 1
    status = "Test"
    print("test")
    send_discord_alert_webhook(chamber, status)