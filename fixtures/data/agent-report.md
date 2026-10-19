# Incident summary TICKET-4127

Root cause: line items were rounded individually before summation,
violating the rounding policy. Fix: round once at the total.
