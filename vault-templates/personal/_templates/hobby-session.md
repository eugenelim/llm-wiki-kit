---
title: "{{Hobby}} — {{focus}}"
type: hobby-session
hobby: {{hobby-slug}}      # links to wiki/hobbies/{slug}/overview.md
date: {{YYYY-MM-DD}}
duration_min: 0            # 0 if you'd rather not track
focus: ""                  # what you worked on (one line)
location: ""               # optional — gym, home, trail, kitchen
mood: ""                   # optional — energized | flat | grinding | flow | frustrated
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [hobby-session, {{hobby-slug}}]
---

## What I Did

{{Concrete description — what was practiced, attempted, completed, observed, sent, drawn, cooked, hiked.}}

## What Worked

{{Wins, breakthroughs, things that clicked. Skip if nothing notable.}}

## What Didn't

{{Sticking points, mistakes, frustrations. Skip if nothing notable.}}

## Next Time

{{The breadcrumb. log-hobby-session writes this back to the hobby's overview.md `## Next Time` so resumption is frictionless.}}
