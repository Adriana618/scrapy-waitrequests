# scrapy-waitrequests

Hey! This is a library for common problems we encounter when dealing with situations that vanilla Scrapy does not fully cover, so here you can find a lot of useful tools.

## Index
- Wait Request

## Wait Request
Wait Request is a method to keep polling for a task's completion—such as a CAPTCHA or batch job—without blocking other requests. You can prepare the initial request along with a function to evaluate whether you have received the desired response. Here is an example:

```python
from scrapy import Spider
from scrapy_algova.wait_request import WaitRequest

class MySpider(Spider):
    name = "my_spider"

    def start_requests(self):
        yield WaitRequest(
            url="https://some.api/endpoint",
            method="POST",
            formdata={"foo": "bar", "captcha_id": "12345"},
            callback=self.parse_result,
            errback=self.handle_error,
            check_condition=self.is_captcha_ready,
            wait_time=3.0,     # Interval (in seconds) before making the next request
            max_tries=5,       # You don't want to check forever, so set a max number of tries
            meta={"info": "extra data"},
            dont_filter=True
        )

    def is_captcha_ready(self, response):
        """
        Check if the response matches what you expect (e.g., a JSON with "status": "OK").
        Otherwise, return False so WaitRequest will retry.
        """
        data = response.json()
        return data.get("status") == "OK"

    def parse_result(self, response):
        """
        Called when 'is_captcha_ready' returns True 
        or when 'max_tries' is reached.
        """
        data = response.json()
        self.logger.info("Task completed! Response data: %s", data)
        # Continue your logic here...

    def handle_error(self, failure):
        """
        Called when there's a network error, a 500 HTTP response, etc.
        """
        self.logger.error("Request failed: %s", failure.value)
```

This approach is far better than using a busy wait with time.sleep(), an infinite while True, or immediately sending repeated requests without any interval. It keeps the reactor free so that other Scrapy requests can run concurrently.