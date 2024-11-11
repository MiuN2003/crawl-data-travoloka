import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chromium.options import ChromiumOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse
from selenium.common.exceptions import NoSuchElementException

# Configure Selenium options to connect to the existing Chrome session
options = ChromiumOptions()
options.add_experimental_option("debuggerAddress", "localhost:8990")
driver = webdriver.Chrome(options=options)

# List of hotel links to scrape
hotel_links = pd.read_csv("Full_Hotel_Traveloka.csv")["hotel_link"].tolist()

# Helper function to retry find_element with retries
def find_element_with_retry(by, value, retries=3, wait=2):
    for attempt in range(retries):
        try:
            element = driver.find_element(by, value)
            return element
        except NoSuchElementException:
            if attempt < retries - 1:
                time.sleep(wait)  # Wait before retrying
            else:
                raise  # Reraise the exception if all retries are exhausted

# Function to extract user ID or mark as anonymous
def get_user_id(i, hotel_link, page_number):
    # Check if user is anonymous by inspecting the specific element's text
    anonymous_xpath = f"//*[@id='section-review-summary']/div[3]/div[3]/div/div[{i}]/div/div[1]/div[1]/div/div[3]"
    anonymous_text = find_element_with_retry(By.XPATH, anonymous_xpath).text

    if "Không tìm thấy trang cá nhân của người dùng ẩn danh này." in anonymous_text or "Đây là tài khoản riêng tư." in anonymous_text:
        return "Ẩn danh"

    # If not anonymous, click to navigate to the user's profile page
    profile_button_xpath = f"""//*[@id="section-review-summary"]/div[3]/div[3]/div/div[{i}]/div/div[1]/div[1]"""
    element = find_element_with_retry(By.XPATH, profile_button_xpath)
    driver.execute_script("arguments[0].click();", element)

    time.sleep(2)  # Wait for the profile page to load
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    # Extract user ID from the URL
    current_url = driver.current_url
    user_id = urlparse(current_url).path.split('/')[-1]
    for k in range(1, 5):
        if user_id == "detail":
            user_id = urlparse(current_url).path.split('/')[-k]
        else:
            break

    # Navigate back to the main page
    driver.get(hotel_link)
    time.sleep(5)  # Adjust sleep for content to load
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    resume_scraping(page_number)

    return user_id

# Function to return to the last viewed comment after navigating back
def resume_scraping(page_number):
    for _ in range(page_number - 1):
        next_button = find_element_with_retry(By.XPATH, "//*[@data-testid='undefined-nextPage']")
        driver.execute_script("arguments[0].click();", next_button)
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")


# Function to scrape comments from a single hotel link
def scrape_hotel_comments(hotel_link):
    # List to hold comments for this hotel
    comments_data = []

    # Open the hotel link
    driver.get(hotel_link)
    time.sleep(5)  # Adjust sleep for content to load
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    page_number = 1  # Track current page for reference

    # Start iterating over comments using XPath
    i = 0
    while True:
        # Move to the next comment
        i += 1
        if i > 10:
            # Check if the 'next page' button is enabled
            try:
                # Locate the 'next page' button using data-testid attribute
                next_button = find_element_with_retry(By.XPATH, "//*[@data-testid='undefined-nextPage']")

                # Check if the button has aria-disabled="true"
                is_disabled = next_button.get_attribute("aria-disabled")

                if is_disabled == "true":
                    # Exit if button is disabled, indicating no more pages left
                    break
                else:
                    # Click the next button to go to the next page
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(1)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    i = 1  # Reset comment index for the new page
                    page_number += 1
            except Exception as e:
                print("Next button not found or another error occurred:", e)
                break

        try:
            # Locate user name, rating, and comment by their XPaths
            # user_name_xpath = f"""//*[@id="section-review-summary"]/div[3]/div[3]/div/div[{i}]/div/div[1]/div[1]/div/div[3]"""
            rating_xpath = f"""//*[@id="section-review-summary"]/div[3]/div[3]/div/div[{i}]/div/div[2]/div[1]/div[1]/div/div[2]"""
            comment_text_xpath = f"""//*[@id="section-review-summary"]/div[3]/div[3]/div/div[{i}]/div/div[2]/div[2]/div/div/div"""

            # user_name = find_element_with_retry(By.XPATH, user_name_xpath).text
            rating = find_element_with_retry(By.XPATH, rating_xpath).text
            comment_text = find_element_with_retry(By.XPATH, comment_text_xpath).text

            # Get user ID
            user_id = get_user_id(i, hotel_link, page_number)

            # Append the data to the list
            comments_data.append({
                # "user_name": user_name,
                "user_id": user_id,
                "rating": rating,
                "comment": comment_text,
                "hotel_link": hotel_link
            })

            print(f"User ID: {user_id}, Rating: {rating}\nComment: {comment_text}\n")

        except Exception as e:
            print("Error occurred while scraping comment:", e)
            continue

    return comments_data


# Collect data from each hotel link
all_comments = []
for link in hotel_links[0:5]:
    hotel_comments = scrape_hotel_comments(link)
    all_comments.extend(hotel_comments)

# Convert the data to a DataFrame and save it to Excel
df = pd.DataFrame(all_comments)
df.drop_duplicates(inplace=True)
df.to_excel("hotel_comments 0 5.xlsx", index=False)

print("Scraping complete. Data saved to 'hotel_comments.xlsx'.")
driver.quit()
