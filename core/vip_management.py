"""Read-only progress indicators and pending-first ordering for VIP rewards."""


def penalty_progress(winners, divisions):
    names = list(dict.fromkeys([*divisions, *(winner.division for winner in winners)]))
    order = {division: index for index, division in enumerate(names)}
    for winner in winners:
        winner.penalty_is_done = bool(winner.penalty_distribution)
        # Count recipients, never attempts. Historic unknown sends are not assumed sent.
        winner.penalty_email_sent = any(email.estado in ('enviado', 'entregado', 'rechazado', 'aplazado')
                                        for email in winner.penalty_emails)

    def summary(label, people):
        total = len(people)
        done = sum(winner.penalty_is_done for winner in people)
        sent = sum(winner.penalty_email_sent for winner in people)
        return {'name': label, 'total': total, 'done': done, 'pending': total-done,
                'sent': sent, 'done_percentage': round(done*100/total) if total else 0,
                'sent_percentage': round(sent*100/total) if total else 0,
                'unknown': sum(not winner.penalty_emails for winner in people)}

    winners.sort(key=lambda winner: (winner.penalty_is_done, order[winner.division], winner.manager.casefold()))
    return {'overall': summary('Total de acertantes', winners),
            'divisions': [summary(division, [winner for winner in winners if winner.division == division])
                          for division in names]}
