import time


def check_order_status(order_id: str) -> str:
    time.sleep(0.05)
    return "processing"


def resolve_refund(order_id: str) -> str:
    status = check_order_status(order_id)
    while status == "processing":
        status = check_order_status(order_id)
    return f"Your refund for order {order_id} is {status}."
