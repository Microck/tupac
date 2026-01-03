# [resource] i built a bot to organize game dev discords because i hate doing it manually

hey r/gamedev,

i’ve been doing game jams and small team projects for a while now, and i noticed i was spending way too much time acting as a discord janitor. every time we started a new prototype or entered a jam, i’d have to manually create the same channel structure (code, art, audio, etc.), set up roles, and fiddle with permissions so the artists didn’t get pinged by backend discussions and vice versa. it was tedious and prone to error.

so i built a tool to automate the whole process.

the idea is pretty simple: you treat your discord server like a studio workspace. when you start a new project, you just run `/newgame "neon drift"`. the bot immediately generates a full suite of ~25 channels organized by discipline—things like `#nd-code-frontend`, `#nd-design-3d`, `#nd-audio-sfx`, etc. it handles all the acronym generation automatically, so "neon drift" becomes "nd", "super smash bros" becomes "ssb", and so on.

the part that actually saves the most time is the role synchronization. instead of manually assigning specific roles for every single project, the bot looks at your server-level roles. if someone is already marked as an `@artist` in your main server, the bot automatically grants them the `@nd-artist` role when the game is created. they instantly get access to the relevant channels for that specific project without you lifting a finger.

i also built in a template system because i know every team has their own workflow. you aren’t locked into the default channel structure i use. you can modify the global template to match your studio’s needs, adding or removing channels as you see fit. there’s even a sync feature, so if you decide halfway through development that every project needs a dedicated `#design-ui` channel, you can update the template and sync it to all active games instantly.

i also found that for smaller teams, using external tools like trello or jira can sometimes be overkill or just create friction because people forget to check them. to fix this, i built a task management system directly into the bot. you can create tasks that spawn discord threads, assign them to team members, and move them through status columns (todo -> in progress -> review -> done) using buttons right inside the chat. it keeps the "to-do list" where the conversation is actually happening.

under the hood, it’s just a python bot using discord.py and sqlite. i’ve containerized it with docker so it’s easy to spin up on a vps or locally if you want to try it out. it’s completely open source (mit license) because i figure other devs probably have the same organization headaches i do.

the repo has a full breakdown of the commands and a setup guide. i’m still actively working on this, so i’m super open to feedback. if you run into any weird bugs or have ideas for how to make the task workflow smoother, definitely let me know here or open an issue on github.

repo: [link to github]

hope it helps organize your chaos a bit.
