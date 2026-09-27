import asyncio
import threading

from flinch.events import MAX_QUEUE, EventBus


def test_publish_from_thread_reaches_subscriber_and_overflow_drops_oldest():
    async def main():
        bus = EventBus()
        q = bus.subscribe()
        t = threading.Thread(target=lambda: bus.publish("decision", {"n": 1}))
        t.start(); t.join()
        msg = await asyncio.wait_for(q.get(), 1)
        assert msg.startswith("event: decision\ndata: ") and msg.endswith("\n\n")
        for i in range(MAX_QUEUE + 10):
            bus.publish("x", {"i": i})
        await asyncio.sleep(0.05)
        assert q.qsize() == MAX_QUEUE
        bus.unsubscribe(q)
        bus.publish("x", {})
        await asyncio.sleep(0.01)
        assert q.qsize() == MAX_QUEUE

    asyncio.run(main())
