# Connect the NetSuite connector

For both AI Jumpstarts Projects, GL Coding Review and P&L Flux. Each person connects once,
with their own NetSuite login, and sets the tool permissions below before the first chat.

## Connect

1. In Claude, open **Customize > Connectors**.
2. Select **NetSuite** under **Your connectors**. Pick production, Unity's live NetSuite
   (account 5602907), not a sandbox. If NetSuite is not listed, ask Unity's Claude admin to
   add it for the organization.
3. Select **Connect**. The NetSuite login opens.
4. Log in to NetSuite as usual. When NetSuite asks for a role, choose the AI read-only role
   Ian created for AI access. Do not choose Administrator or the role you use day to day.
5. Back in Claude, NetSuite shows as **Connected**.
6. Set the tool permissions, below, before you use it.
7. In the close's chat, select **+** in the message box, then **Connectors**, and turn
   NetSuite on.

## Tool permissions

On the same page, **Customize > Connectors > NetSuite**, under **Tool permissions**:

| Tools | Setting | Why |
|---|---|---|
| Read tools: searches, saved searches, reports, SuiteQL queries, record look-ups | **Always allow** | This is all the Projects use: the month's link IDs, and a look-up to see that a fix or an accrual is in NetSuite |
| Write and delete tools: create, update or delete a record | **Blocked** | Claude never writes to NetSuite. Entries reach it through the NetSuite import, which a person imports |

If a tool is listed on its own and you are not sure which kind it is, block it. If Claude asks
to use a tool that would change a record, do not allow it.

## Can Claude write to NetSuite if my own login can?

No. With these settings Claude cannot write to NetSuite, even if your own login can post and
edit. You block the write and delete tools yourself. The connection runs on the AI read-only
role, so NetSuite itself refuses a change. And both Projects tell Claude to use read tools
only, and that only the reviewer settles an item. Unity's Claude admin can also block those
tools for the whole organization; once the admin blocks a tool, no one can turn it back on.

## If it fails

* **The login fails with a role error.** Log out of NetSuite in every browser tab, then go
  back to **Customize > Connectors** and select **Connect** again. When NetSuite asks for a
  role, choose the AI read-only role.
* **It still fails.** Take a screenshot of the error and send it to the NetSuite admin. They
  can check that your login has the AI read-only role. Do not ask for a role with more access.
* **NetSuite shows Reconnect.** Select it and log in again.
* **Claude says it has no NetSuite tools.** Check that NetSuite is turned on in the chat's
  **+** menu, under **Connectors**.

Until the connector works, run the month as usual. The GL still comes from the saved search
export. Without the connector, the console's document numbers are plain text, with no links.
