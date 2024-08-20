import argparse
import asyncio
import aiohttp
import time
from aiohttp import ClientSession
from concurrent.futures import ThreadPoolExecutor

async def send_request(session, url, request_type, content):
    try:
        if request_type.lower() == "post":
            async with session.post(url, data=content) as response:
                await response.text()
        elif request_type.lower() == "get":
            async with session.get(url) as response:
                await response.text()
        else:
            raise ValueError("Unsupported request type")
        return True
    except Exception as e:
        print(f"Request failed: {e}")
        return False

async def stress_test(args):
    url = args.endpoint
    request_type = args.type
    content = args.content
    num_users = args.concurrent_users
    requests_per_sec = args.requests_per_sec

    success_count = 0
    failure_count = 0

    async with ClientSession() as session:
        tasks = []
        for _ in range(num_users):
            for _ in range(requests_per_sec):
                task = send_request(session, url, request_type, content)
                tasks.append(task)
            await asyncio.sleep(1)  # Wait 1 second before starting the next batch of requests

        results = await asyncio.gather(*tasks)

    for result in results:
        if result:
            success_count += 1
        else:
            failure_count += 1

    total_requests = success_count + failure_count
    failure_rate = (failure_count / total_requests) * 100 if total_requests > 0 else 0

    print(f"Total Requests: {total_requests}")
    print(f"Successful Requests: {success_count}")
    print(f"Failed Requests: {failure_count}")
    print(f"Failure Rate: {failure_rate:.2f}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stress test.")
    parser.add_argument("--endpoint", type=str, required=True, help="The API endpoint to test")
    parser.add_argument("--type", type=str, default="post", help="The type of HTTP request (GET or POST)")
    parser.add_argument("--content", type=str, help="The content to send in the request body for POST requests")
    parser.add_argument("--concurrent_users", type=int, default=1, help="Number of concurrent users")
    parser.add_argument("--requests_per_sec", type=int, default=1, help="Number of requests per second per user")

    args = parser.parse_args()

    asyncio.run(stress_test(args))






import requests
import time

url = "http://127.0.0.1:80/on-prem-llm/generate"
headers = {
    "Content-Type": "application/json"
}
data = {
    # "query": "Hello my name is david."
    "query": "Context: Architecturally, the school has a Catholic character. Atop the Main Building's gold dome is a golden statue of the Virgin Mary. Immediately in front of the Main Building and facing it, is a copper statue of Christ with arms upraised with the legend \"Venite Ad Me Omnes\". Next to the Main Building is the Basilica of the Sacred Heart. Immediately behind the basilica is the Grotto, a Marian place of prayer and reflection. It is a replica of the grotto at Lourdes, France where the Virgin Mary reputedly appeared to Saint Bernadette Soubirous in 1858. At the end of the main drive (and in a direct line that connects through 3 statues and the Gold Dome), is a simple, modern stone statue of Mary. \n Question: To whom did the Virgin Mary allegedly appear in 1858 in Lourdes France?"
}

queries = [
    "Context: The university is the major seat of the Congregation of Holy Cross (albeit not its official headquarters, which are in Rome). Its main seminary, Moreau Seminary, is located on the campus across St. Joseph lake from the Main Building. Old College, the oldest building on campus and located near the shore of St. Mary lake, houses undergraduate seminarians. Retired priests and brothers reside in Fatima House (a former retreat center), Holy Cross House, as well as Columba Hall near the Grotto. The university through the Moreau Seminary has ties to theologian Frederick Buechner. While not Catholic, Buechner has praised writers from Notre Dame and Moreau Seminary created a Buechner Prize for Preaching. Question: Where is the headquarters of the Congregation of the Holy Cross?",
    "Context: Architecturally, the school has a Catholic character. Atop the Main Building's gold dome is a golden statue of the Virgin Mary. Immediately in front of the Main Building and facing it, is a copper statue of Christ with arms upraised with the legend \"Venite Ad Me Omnes\". Next to the Main Building is the Basilica of the Sacred Heart. Immediately behind the basilica is the Grotto, a Marian place of prayer and reflection. It is a replica of the grotto at Lourdes, France where the Virgin Mary reputedly appeared to Saint Bernadette Soubirous in 1858. At the end of the main drive (and in a direct line that connects through 3 statues and the Gold Dome), is a simple, modern stone statue of Mary. \n Question: To whom did the Virgin Mary allegedly appear in 1858 in Lourdes France?",
    "Context: The Joan B. Kroc Institute for International Peace Studies at the University of Notre Dame is dedicated to research, education and outreach on the causes of violent conflict and the conditions for sustainable peace. It offers PhD, Master's, and undergraduate degrees in peace studies. It was founded in 1986 through the donations of Joan B. Kroc, the widow of McDonald's owner Ray Kroc. The institute was inspired by the vision of the Rev. Theodore M. Hesburgh CSC, President Emeritus of the University of Notre Dame. The institute has contributed to international policy discussions about peace building practices. Question: In what year was the Joan B. Kroc Institute for International Peace Studies founded?",
    "Context: Notre Dame is known for its competitive admissions, with the incoming class enrolling in fall 2015 admitting 3,577 from a pool of 18,156 (19.7%). The academic profile of the enrolled class continues to rate among the top 10 to 15 in the nation for national research universities. The university practices a non-restrictive early action policy that allows admitted students to consider admission to Notre Dame as well as any other colleges to which they were accepted. 1,400 of the 3,577 (39.1%) were admitted under the early action plan. Admitted students came from 1,311 high schools and the average student traveled more than 750 miles to Notre Dame, making it arguably the most representative university in the United States. While all entering students begin in the College of the First Year of Studies, 25% have indicated they plan to study in the liberal arts or social sciences, 24% in engineering, 24% in business, 24% in science, and 3% in architecture. Question: What percentage of students were admitted to Notre Dame in fall 2015?",
    "Context: One of the main driving forces in the growth of the University was its football team, the Notre Dame Fighting Irish. Knute Rockne became head coach in 1918. Under Rockne, the Irish would post a record of 105 wins, 12 losses, and five ties. During his 13 years the Irish won three national championships, had five undefeated seasons, won the Rose Bowl in 1925, and produced players such as George Gipp and the \"Four Horsemen\". Knute Rockne has the highest winning percentage (.881) in NCAA Division I/FBS football history. Rockne's offenses employed the Notre Dame Box and his defenses ran a 7–2–2 scheme. The last game Rockne coached was on December 14, 1930 when he led a group of Notre Dame all-stars against the New York Giants in New York City. Question: The Notre Dame football team got a new head coach in 1918, who was it?",
]

total_time = 0
total_tokens = 0
for i in range(10):
    start = time.time()
    response = requests.post(
        url, 
        headers=headers, 
        json={"query": queries[i % len(queries)]},
    )
    end = time.time()
    total_time += end - start
    total_tokens += (len(data["query"].split(" ")) + len(response.text.split(" "))) * 1.25
    print(total_tokens)

print(total_time / 10)
print(total_tokens / total_time)



