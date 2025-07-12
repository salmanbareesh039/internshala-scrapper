import asyncio
import aiohttp
import time
import json
from tqdm import tqdm
from bs4 import BeautifulSoup
import re
import hashlib
import os
from apify_client import ApifyClient
from apify import Actor

# For Selenium (as fallback)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

class ImprovedInternshalaScraperWithMaxResults:
    def __init__(self, base_url, max_results=50, pages_to_scrape=20):
        self.base_url = base_url
        self.max_results = max_results
        self.pages_to_scrape = pages_to_scrape
        self.all_internships = []
        self.visited_hashes = set()  # To track duplicates
        self.valid_internship_count = 0
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://internshala.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def generate_urls(self):
        """Generate URLs for all pages to be scraped, limited by max_results"""
        urls = []
        estimated_internships_per_page = 10  # Approximate number of internships per page

        # Calculate how many pages we need to reach max_results
        required_pages = min(
            self.pages_to_scrape,
            max(1, (self.max_results + estimated_internships_per_page - 1) // estimated_internships_per_page)
        )

        for page in range(1, required_pages + 1):
            if page == 1:
                urls.append(self.base_url.rstrip('/'))
            else:
                urls.append(f"{self.base_url.rstrip('/')}/page-{page}")
        return urls

    def generate_hash(self, internship):
        """Generate a unique hash for an internship to detect duplicates"""
        hash_string = f"{internship.get('title', '')}-{internship.get('company', '')}-{internship.get('location', '')}"
        return hashlib.md5(hash_string.encode()).hexdigest()

    def parse_internship_card(self, card):
        """Extract data from a single internship card with improved parsing"""
        try:
            # Helper function to safely extract text with better defaults
            def get_text(selector, default=None):
                elements = card.select(selector)
                for element in elements:
                    if element:
                        text = element.text.strip()
                        # Clean up any extra whitespace and newlines
                        text = re.sub(r'\s+', ' ', text).strip()
                        # Only return if it has actual content
                        if text and text != "Not specified" and len(text) > 0:
                            # Further cleanup: check for "Actively hiring" text in company name
                            if "Actively hiring" in text and "company" in selector:
                                text = text.replace("Actively hiring", "").strip()
                            return text
                return default

            # Helper function to safely extract attribute
            def get_attr(selector, attr, default=None):
                elements = card.select(selector)
                for element in elements:
                    if element and attr in element.attrs:
                        value = element[attr]
                        if value and value != "Not specified" and len(value) > 0:
                            return value
                return default

            # Build internship data with more robust parsing
            internship_data = {}

            # Get primary fields with multiple selectors
            # Use broader selectors and check multiple elements
            title_selectors = [
                ".job-title-href", ".profile", "h3.heading", ".view_detail_button",
                ".view-detail", "a[title]", ".heading a", ".internship-title", ".profile"
            ]

            company_selectors = [
                ".company-name", ".company_name", ".company_and_premium",
                ".company-text", ".company_text", ".company"
            ]

            location_selectors = [
                ".locations a", ".location_names", ".location_link", ".location",
                ".location-name", ".internship_other_details_container .location_names"
            ]

            # Extract text using our improved selectors
            title = None
            job_url = None
            
            # First try to get job URL from job-title-href
            job_title_element = card.select_one(".job-title-href")
            if job_title_element:
                title = job_title_element.text.strip()
                title = re.sub(r'\s+', ' ', title).strip()
                
                # Extract href for job URL
                href = job_title_element.get('href')
                if href:
                    # Make sure it's a full URL
                    if href.startswith('/'):
                        job_url = f"https://internshala.com{href}"
                    elif not href.startswith('http'):
                        job_url = f"https://internshala.com/{href}"
                    else:
                        job_url = href
            
            # If we didn't get title from job-title-href, try other selectors
            if not title:
                for selector in title_selectors:
                    title = get_text(selector, title)
                    if title:
                        break

            company = None
            for selector in company_selectors:
                company = get_text(selector, company)
                if company:
                    # Clean up any "Actively hiring" text that might be in the company name
                    company = re.sub(r'Actively\s+hiring', '', company).strip()
                    break

            location = None
            for selector in location_selectors:
                location = get_text(selector, location)
                if location:
                    break

            # Only proceed if we have the key fields
            if not (title and company):
                return None

            internship_data["title"] = title
            internship_data["company"] = company

            # Add job URL if we found it
            if job_url:
                internship_data["job_url"] = job_url
                # Generate apply link by adding the referral parameter
                internship_data["apply_link"] = f"{job_url}?amp;referral=web_share"

            # Add location if available
            if location:
                internship_data["location"] = location

            # Get additional fields with improved selectors
            duration_selectors = [
                ".ic-16-calendar + span", ".duration",
                ".internship_other_details_container span:nth-child(1)",
                ".other_detail_item span", ".internship-detail span:contains('Duration')",
                "span:contains('Duration')"
            ]

            stipend_selectors = [
                ".stipend", ".stipend_container", ".internship_other_details_container span:nth-child(2)",
                ".stipend-text", "span:contains('Stipend')", ".stipend_text"
            ]

            experience_selectors = [
                ".ic-16-briefcase + span", ".experience",
                ".row-1-item .ic-16-briefcase + span",
                ".other_detail_item .ic-16-briefcase + span",
                ".internship-detail .ic-16-briefcase + span",
                "span:contains('year')", "span:contains('month')",
                ".experience-text", ".experience_text"
            ]

            # Extract other details
            duration = None
            for selector in duration_selectors:
                duration = get_text(selector, duration)
                if duration:
                    # Clean up the duration text to remove any labels
                    duration = re.sub(r'^Duration\s*:', '', duration).strip()
                    break

            stipend = None
            for selector in stipend_selectors:
                stipend = get_text(selector, stipend)
                if stipend:
                    # Clean up the stipend text to remove any labels
                    stipend = re.sub(r'^Stipend\s*:', '', stipend).strip()
                    break

            experience = None
            for selector in experience_selectors:
                experience = get_text(selector, experience)
                if experience:
                    # Clean up the experience text to remove any labels
                    experience = re.sub(r'^Experience\s*:', '', experience).strip()
                    # Handle different experience formats
                    if 'year' in experience.lower() or 'month' in experience.lower():
                        # Clean up common patterns like "1 year(s)" to "1 year"
                        experience = re.sub(r'\(s\)', '', experience)
                        experience = re.sub(r'\s+', ' ', experience).strip()
                        break

            # Add cleaned duration, stipend, and experience if available
            if duration:
                internship_data["duration"] = duration

            if stipend:
                internship_data["stipend"] = stipend

            if experience:
                internship_data["experience"] = experience

            # Boolean fields - check multiple class names
            actively_hiring_selectors = [
                ".actively-hiring-badge", ".actively_hiring_badge",
                ".actively-hiring", "span:contains('Actively hiring')",
                ".badge-actively-hiring", ".actively_hiring"
            ]

            early_applicant_selectors = [
                ".early_applicant_wrapper", ".early-applicant",
                ".early_applicant", "span:contains('Be an early applicant')"
            ]

            # Check for actively hiring badge
            for selector in actively_hiring_selectors:
                if card.select(selector):
                    internship_data["actively_hiring"] = True
                    break

            # Look for text indicating "Actively hiring"
            card_text = card.text.lower()
            if "actively hiring" in card_text:
                internship_data["actively_hiring"] = True

            # Check for early applicant badge
            for selector in early_applicant_selectors:
                if card.select(selector):
                    internship_data["early_applicant"] = True
                    break

            # Look for "early applicant" text
            if "early applicant" in card_text or "be an early applicant" in card_text:
                internship_data["early_applicant"] = True

            # Add other fields if available
            internship_type_selectors = [
                ".gray-labels .status-li span", ".internship_label", ".label_container span",
                ".badge-container span", ".label-container span", "span.badge"
            ]

            posted_selectors = [
                ".status-inactive span", ".posted_by_container", ".posted span",
                ".posted-by", ".posted_by", ".posted-on", ".posted_on"
            ]

            # Get internship type
            internship_type = None
            for selector in internship_type_selectors:
                internship_type = get_text(selector, internship_type)
                if internship_type:
                    break

            if internship_type:
                internship_data["type"] = internship_type

            # Get posted date/info
            posted = None
            for selector in posted_selectors:
                posted = get_text(selector, posted)
                if posted:
                    break

            if posted:
                internship_data["posted"] = posted

            # Get logo
            logo_selectors = [
                ".internship_logo img", ".company_logo img",
                ".logo img", ".company-logo img", ".internship-logo img"
            ]

            logo_url = None
            for selector in logo_selectors:
                logo_url = get_attr(selector, "src", logo_url)
                if logo_url:
                    break

            if logo_url:
                # Make sure it's a full URL
                if not logo_url.startswith("http") and not logo_url.startswith("/"):
                    logo_url = f"/{logo_url}"
                internship_data["logo_url"] = logo_url

            # If we didn't get job_url from job-title-href, try other link selectors
            if not job_url:
                link_selectors = [
                    "a.view_detail_button", "a.apply_button",
                    "a.view-detail-button", "a.view-detail", "a.view_detail",
                    ".view-detail a", ".apply a", ".apply_now a", "a.apply_now"
                ]

                for selector in link_selectors:
                    href = get_attr(selector, "href")
                    if href:
                        # Make sure it's a full URL
                        if href.startswith('/'):
                            job_url = f"https://internshala.com{href}"
                        elif not href.startswith('http'):
                            job_url = f"https://internshala.com/{href}"
                        else:
                            job_url = href
                        
                        internship_data["job_url"] = job_url
                        internship_data["apply_link"] = f"{job_url}?amp;referral=web_share"
                        break

            return internship_data

        except Exception as e:
            print(f"Error parsing card: {str(e)}")
            return None

    async def fetch_page_async(self, session, url):
        """Fetch a page asynchronously using aiohttp"""
        try:
            async with session.get(url, headers=self.headers, timeout=30) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"Failed to fetch {url}: Status {response.status}")
                    return None
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return None

    def scrape_page_with_selenium(self, url):
        """Fallback method using Selenium if needed"""
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            options.binary_location = "/usr/bin/chromium"
            # Try to use default Service, fallback to chromedriver in PATH
            try:
                driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
            except Exception:
                driver = webdriver.Chrome(options=options)  # Fallback if Service() fails

            driver.get(url)
            time.sleep(5)  # Wait for page to load
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            html = driver.page_source
            driver.quit()
            return html
        except Exception as e:
            print(f"Selenium error on {url}: {str(e)}")
            return None

    def process_html(self, html, url):
        """Process HTML content and extract internships with improved selectors"""
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")

        # Try multiple selectors for internship cards
        card_selectors = [
            # Standard selectors
            ".individual_internship", ".internship_meta", ".internship-container",
            ".container-fluid .internship_list",
            # More specific selectors
            ".internship_list_container .individual_internship",
            ".internship-container .internship",
            ".internships-list .internship-container",
            # Generic fallback selectors
            "div[class*='internship']", "div[class*='job']",
            ".internship_list > div", ".internships > div",
            # Catch-all for list items
            ".internship-list > div", ".internship_list li", ".internships li"
        ]

        # Try each selector to find cards
        cards = []
        for selector in card_selectors:
            cards = soup.select(selector)
            if cards and len(cards) > 0:
                print(f"Found {len(cards)} cards using selector: {selector}")
                break

        if not cards:
            # If still no cards found, try to capture any divs with specific text content
            print(f"Warning: No cards found with standard selectors on {url}")
            print("Trying text-based detection...")

            # Look for elements likely to be internship cards based on content
            potential_divs = soup.find_all('div')
            cards = []

            for div in potential_divs:
                # Check if div contains key internship indicators
                text = div.text.lower()
                if (("internship" in text or "job" in text) and
                    ("stipend" in text or "salary" in text or "month" in text) and
                    ("duration" in text or "location" in text)):
                    cards.append(div)

            if cards:
                print(f"Found {len(cards)} potential cards using text-based detection")
            else:
                print(f"Warning: No cards found on {url} with any detection method")
                return []

        # Debug output
        print(f"Processing {len(cards)} cards from {url}")

        # Process all cards on this page
        for card in cards:
            # Stop if we've reached max_results
            if self.valid_internship_count >= self.max_results:
                break

            internship_data = self.parse_internship_card(card)
            if not internship_data:
                continue

            # Check for duplicate using hash
            card_hash = self.generate_hash(internship_data)
            if card_hash in self.visited_hashes:
                continue

            # Add the internship and its hash
            self.visited_hashes.add(card_hash)
            self.all_internships.append(internship_data)
            self.valid_internship_count += 1

            # Debug output for successful extraction
            job_url = internship_data.get('job_url', 'No URL')
            apply_link = internship_data.get('apply_link', 'No apply link')
            experience = internship_data.get('experience', 'No experience specified')
            print(f"Extracted internship: {internship_data.get('title')} at {internship_data.get('company')}")
            print(f"  Job URL: {job_url}")
            print(f"  Apply Link: {apply_link}")
            print(f"  Experience: {experience}")

            # Stop if we've reached max_results
            if self.valid_internship_count >= self.max_results:
                print(f"Reached max results limit ({self.max_results})")
                break

        return []

    async def scrape_page(self, url):
        """Scrape a single page"""
        try:
            async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
                html = await self.fetch_page_async(session, url)

                # If aiohttp fails, fall back to Selenium
                if not html:
                    print(f"Falling back to Selenium for {url}")
                    html = self.scrape_page_with_selenium(url)

                return self.process_html(html, url)

        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            return []

    async def scrape_all_pages_async(self):
        """Scrape all pages asynchronously"""
        urls = self.generate_urls()

        # Create tasks for each URL
        tasks = []
        for url in urls:
            if self.valid_internship_count >= self.max_results:
                break
            tasks.append(self.scrape_page(url))

        # Process tasks as they complete
        for task in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Scraping pages"):
            if self.valid_internship_count >= self.max_results:
                break

            try:
                await task  # process_html now appends directly to self.all_internships
            except Exception as e:
                print(f"Error in async task: {str(e)}")

        return self.all_internships

    def run_scraper(self):
        """Execute the scraping process"""
        start_time = time.time()
        print(f"Starting scraper to collect up to {self.max_results} internships...")
        # Run the async event loop
        try:
            # Use asyncio.run if possible (Python 3.7+)
            try:
                self.all_internships = asyncio.run(self.scrape_all_pages_async())
            except RuntimeError:
                # Fallback for environments where asyncio.run() cannot be called (e.g., nested event loop)
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                self.all_internships = loop.run_until_complete(self.scrape_all_pages_async())
        except Exception as e:
            print(f"Error in async execution: {str(e)}")
            print("Falling back to synchronous execution...")
            urls = self.generate_urls()
            self.all_internships = []
            with tqdm(total=len(urls), desc="Scraping pages (sync fallback)") as pbar:
                for url in urls:
                    if self.valid_internship_count >= self.max_results:
                        break
                    html = self.scrape_page_with_selenium(url)
                    results = self.process_html(html, url)
                    self.all_internships.extend(results)
                    pbar.update(1)
        end_time = time.time()
        print(f"Scraping completed in {end_time - start_time:.2f} seconds")
        print(f"Total internships scraped: {len(self.all_internships)} (target: {self.max_results})")
        self.clean_results()
        return self.all_internships

    def clean_results(self):
        """Clean up the scraped data to fix any issues"""
        for internship in self.all_internships:
            # Fix company names with "Actively hiring" text
            if "company" in internship:
                company = internship["company"]
                company = re.sub(r'Actively\s+hiring', '', company).strip()
                internship["company"] = company

            # Ensure boolean fields are properly set
            if "actively_hiring" not in internship:
                internship["actively_hiring"] = False

            if "early_applicant" not in internship:
                internship["early_applicant"] = False

    def save_results(self, filename=None):
        """Save the results using Apify Actor.push_data instead of JSON/CSV"""
        # This method is now unused, but kept for compatibility
        pass

async def main():
    async with Actor:
        # Get input from Apify (expects input like { "job_category": "Data Science", "work_from_home": "yes", ... })
        input_data = await Actor.get_input() or {}
        
        # Debug: Print the input data to see what's being received
        print(f"Input data received: {input_data}")

        # Extract parameters from input with better error handling
        job_category = input_data.get('job_category')
        if not job_category:
            print("Warning: No job_category provided, using default 'Data Science'")
            job_category = 'Data Science'  # Changed default from 'Accounts'
        
        work_from_home = input_data.get('work_from_home')
        if work_from_home is None:
            print("Warning: No work_from_home provided, using default 'no'")
            work_from_home = 'no'  # Changed default from 'yes' to 'no'
        
        location = input_data.get('location')
        if location is None:
            print("Warning: No location provided, using empty string")
            location = ''
        
        part_time = input_data.get('part_time')
        if part_time is None:
            print("Warning: No part_time provided, using default 'no'")
            part_time = 'no'
        
        stipend = input_data.get('stipend')
        if stipend is None:
            print("Warning: No stipend provided, using empty string")
            stipend = ''
        
        max_results_input = input_data.get('max_results')
        if max_results_input is None:
            print("Warning: No max_results provided, using default 30")
            max_results = 30
        else:
            try:
                max_results = int(max_results_input)
            except (ValueError, TypeError):
                print(f"Warning: Invalid max_results value '{max_results_input}', using default 30")
                max_results = 30

        # Debug: Print extracted parameters
        print(f"Job Category: {job_category}")
        print(f"Work from Home: {work_from_home}")
        print(f"Location: {location}")
        print(f"Part Time: {part_time}")
        print(f"Stipend: {stipend}")
        print(f"Max Results: {max_results}")

        # Generate URL
        url = generate_url(
            job_category=job_category,
            work_from_home=work_from_home,
            location=location,
            part_time=part_time,
            stipend=stipend
        )

        print(f"Generated URL: {url}")

        # Run the scraper
        scraper = ImprovedInternshalaScraperWithMaxResults(base_url=url, max_results=max_results)
        results = scraper.run_scraper()
        
        # Push results to Apify
        for internship_data in results:
            await Actor.push_data(internship_data)

def slugify(text):
    return text.lower().replace('.', '').replace(' ', '-')

def generate_url(job_category=None, work_from_home=None, location=None, part_time=None, stipend=None):
    # Allow passing parameters for automation/testing
    if job_category is None:
        job_category = input("Enter job category (e.g., Accounts, NET Development): ")
    if work_from_home is None:
        work_from_home = input("Work from home? (yes/no): ").lower()

    if location is None and work_from_home == "no":
        location = input("Enter location (Delhi, Mumbai, Chennai): ").lower()
    elif work_from_home == "yes":
        location = ""

    if part_time is None:
        part_time = input("Part-time job? (yes/no): ").lower()
    if stipend is None:
        stipend = input("Minimum stipend? (Leave blank if not applicable): ")

    category_slug = slugify(job_category)

    if part_time == "yes" and stipend.isdigit():
        return f"https://internshala.com/internships/part-time-{category_slug}-jobs/stipend-{stipend}/"
    elif part_time == "yes":
        return f"https://internshala.com/internships/part-time-{category_slug}-jobs/"
    elif work_from_home == "yes":
        return f"https://internshala.com/internships/work-from-home-{category_slug}-internships/"
    elif work_from_home == "no":
        return f"https://internshala.com/internships/{category_slug}-internship-in-{location}/"
    # Fallback — always return something
    return f"https://internshala.com/internships/{category_slug}-internship/"

# Only run if this script is executed directly
if __name__ == "__main__":
    asyncio.run(main())
