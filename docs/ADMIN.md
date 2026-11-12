# Administration

Primary administrators are the server owner, OWNER_IDS and configured primary_users. Moderators are members of configured manager_roles. Roles are fetched fresh for each authorization; a stale interaction member object is not a permission grant.

| Command | Scope | Use |
| --- | --- | --- |
| /ripper panel | Member | Open a private panel |
| /ripper admin | Moderator | Open operation forms and tools |
| /ripper setup | Primary | Seven-step channel/access wizard; optional three-role step |
| /ripper doctor | Moderator | Private JSON health, permissions, consistency and recovery report |
| /ripper snapshot | Moderator | Preview and confirm finalized Rumble/ordinary-raffle participation |
| /ripper task_snapshot | Moderator | Preview accepted task contributors for a cycle |
| /ripper task_reward | Moderator | Review and pay one member's task/cycle, including offline posts |
| /ripper task_manage | Moderator | List, close/archive, cooldown/reset, resend brief; thread binding is primary-only |
| /ripper raffle_manage | Moderator | List, publish, close, cancel, delivered, forfeit, replace and refresh; message binding is primary-only |
| /ripper correction | Primary | Confirm a signed integer adjustment with reason |
| /ripper revoke_reward | Primary | Confirm reversal of a specific invalid original reward |
| /ripper settings_export | Primary | Export settings without runtime message IDs |
| /ripper settings_import | Primary | Validate and preview changed fields, then confirm |
| /ripper settings_history | Primary | List or validate/restore one of 30 retained previous configurations |
| /ripper report | Moderator | CSV: leaderboard, ledger, tasks, raffles or audit |
| /ripper access | Primary | Set primary user IDs, manager role IDs or optional spin role |
| /ripper reactions | Primary | Configure/remove base or quality reward reactions |
| /ripper panel_recover | Primary | Bind a known application-owned panel/leaderboard message |
| /ripper leaderboard_publish | Primary | Publish once or refresh the public leaderboard |
| /ripper recovery | Primary | Retry failed jobs, verify/unpause accounting, request bounded restart, mark a confirmed deleted panel missing |

## Daily workflow

Create tasks through the admin panel. Approve valid posts with ✅. Award 🏅 deliberately when quality merits a separate bonus. A quality snapshot is an additional award operation, not an alternative label for the base reward. Re-running a new quality snapshot deliberately adds another bonus; repeating the same confirmation does not.

Use task_manage list to find cycle IDs. Use task_snapshot for all accepted members in one cycle, or task_reward for a specific reviewed contribution. Snapshot and reaction base awards use the same task/cycle/member identity.

Ordinary event participation is paid only after importing and confirming the source export. An already-paid event cannot be silently edited by reuploading a different list or amount. Use correction or revoke_reward to fix a reviewed mistake.

Check raffle_manage list for delayed closes or publication errors. A closing raffle retains reserved RC until eligibility checks succeed. Cancellation is available before closing starts; an already-closing raffle needs its eligibility failure resolved before settlement. A completed draw is final. Replacement requires an explicitly forfeited, undelivered prize.

Use report ledger to find a reward's ledger ID. Use revoke_reward to invalidate that contribution and its task/event metric. Use correction for a general amount adjustment. Both preserve history and actor/reason.

## Setup details

Five channel selections are required before activation. Re-running the wizard changes selections without clearing accounts. Skip disables achievement-role assignment and hides My Progress. Existing achievement-role definitions remain editable for later activation.

Achievement role form fields are:

```text
role ID, minimum lifetime earned RC, minimum rewarded task cycles, minimum paid events
```

All three metric thresholds must be nondecreasing between tiers, and at least one must increase. Every tier must require at least one nonzero metric. Select existing roles with zero permissions. The bot refuses managed/default roles, access/spin/staff collisions, foreign coordination bindings and roles at/above the bot.

Sensitive program controls require a primary administrator even if a moderator opens their form. Permission checks repeat on submission/confirmation. Members cannot use another member's private screen.

Private panels expire after ten minutes. Reopen the public panel or /ripper panel. Public panel and raffle button identities are restored on restart.

## Ambiguous publication

Financial decisions are durable. Discord sends are separate network operations, so a timeout does not prove that no message/thread was created.

| Uncertain effect | Recovery |
| --- | --- |
| Member panel send | Find its application-owned message and use panel_recover |
| Leaderboard send | Find its message and use panel_recover kind leaderboard |
| Task thread creation | Find the thread and use task_manage bind_thread |
| RC raffle public post | Find the matching post and use raffle_manage bind_message |
| Raffle result update | Retry refresh; original result and ticket settlement remain unchanged |
| Recovery pulse post | Stop helper, find the post, use local rzctl bind-recovery, restart helper |

If no panel exists after manual inspection, the local operator tool supports an explicit verified-missing review. Automatic recovery does not guess that an uncertain send failed. A primary administrator may cancel an unbound RC raffle draft/publication and create a new one after confirming that no valid post should remain.
