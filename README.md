# Internshala Internship Scraper

## 🤖 Overview

This Apify actor scrapes internship listings from Internshala.com based on custom filters like job category, location, work-from-home preferences, and more. With this actor, you can easily collect detailed information about internships and use the data for research, job hunting, aggregation services, or any other purpose.

## ✅ Features

- **Customizable Search**: Filter internships by job category, location, work-from-home status, part-time availability, and minimum stipend
- **Detailed Data**: Collects comprehensive information about each internship, including job title, company name, location, stipend, duration, and more
- **Duplicate Prevention**: Built-in logic to avoid collecting duplicate internship listings
- **Robust Parsing**: Advanced parsing algorithms to handle website changes and ensure reliable data extraction
- **Pagination Support**: Automatically navigates through multiple pages to collect all relevant listings
- **Rate Limiting**: Implements respectful scraping practices to avoid overloading the target website

## 📋 Input Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_results` | Integer | Maximum number of internships to collect (default: 30) |
| `job_category` | String | Category of internships to search for (e.g., "Software Development", "Marketing") |
| `work_from_home` | Boolean | Whether to search for work-from-home internships |
| `location` | String | Location for internships (used if work_from_home is false) |
| `part_time` | Boolean | Whether to search for part-time internships |
| `stipend` | String | Minimum stipend requirement (leave empty if not applicable) |
| `pages_to_scrape` | Integer | Maximum number of pages to scrape (default: 20) |

## 📊 Output Data Structure

Each internship object contains the following fields (when available):

```json
{
    "title": "Software Development Intern",
    "company": "Tech Solutions Ltd",
    "location": "Delhi",
    "duration": "3 months",
    "stipend": "₹10,000 /month",
    "actively_hiring": true,
    "early_applicant": false,
    "type": "Internship",
    "posted": "Posted 2 days ago",
    "apply_link": "https://internshala.com/internship/detail/...",
    "logo_url": "https://internshala.com/uploads/logo/..."
}
```

## 💰 Usecase of This Actor

1. **Job Aggregation Websites**: Create a niche job portal focused on internships and early-career opportunities
2. **Subscription Services**: Offer premium internship alerts or reports to students and job seekers
3. **Data Analysis**: Sell insights on internship trends, popular skills, and compensation patterns
4. **College & University Services**: Partner with educational institutions to provide customized internship feeds
5. **Integration Services**: Build APIs or plugins that integrate this data with career portals, student management systems, or HR software
6. **Custom Search Tools**: Create specialized search engines for students looking for internships with specific criteria
7. **Content Marketing**: Use the data to generate articles about internship opportunities, trends, and advice
8. **Lead Generation**: Sell qualified leads to companies looking to hire interns in specific fields
