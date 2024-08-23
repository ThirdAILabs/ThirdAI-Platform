import time
from dataclasses import dataclass


@dataclass
class SecondCount:
    timestamp: int
    count: int


class Throughput:
    def __init__(self):
        self.past_hour_history = [SecondCount(0, 0) for _ in range(3600)]
        self.past_hour_total = 0
        self.since_beginning_total = 0

    def log(self, amount=1):
        timestamp = int(time.time())
        idx = timestamp % len(self.past_hour_history)
        if self.past_hour_history[idx].timestamp == timestamp:
            self.past_hour_total += amount
            self.past_hour_history[idx].count += amount
        else:
            self.past_hour_total -= self.past_hour_history[idx].count
            self.past_hour_total += amount
            self.past_hour_history[idx] = SecondCount(timestamp, amount)
        self.since_beginning_total += amount

    def past_hour(self):
        return self.past_hour_total

    def since_beginning(self):
        return self.since_beginning_total
