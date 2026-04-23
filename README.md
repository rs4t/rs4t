.__    .__      .__/\                              __   
|  |__ |__|     |__)/_____   _______  ______ _____/  |_ 
|  |  \|  |     |  |/     \  \_  __ \/  ___// __ \   __\
|   Y  \  |     |  |  Y Y  \  |  | \/\___ \\  ___/|  |  
|___|  /__| /\  |__|__|_|  /  |__|  /____  >\___  >__|  
     \/     )/           \/              \/     \/      
                    i make stuff

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

> student • automation • design • minecraft • code

I like building useful things, automating annoying stuff,
and making clean systems that actually make sense.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## about me

- based in Switzerland
- interested in bots, automation, backend stuff
- minecraft server projects
- physics + math enjoyer
- sometimes frontend if i feel brave enough
- professional procrastinator

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## current projects

→ minecraft server systems  
→ username checker tools  
→ automation scripts  
→ discord integrations  
→ random side projects at 2am

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## github metrics

<p align="center">
  <img src="/github-metrics.svg" alt="Metrics">
</p>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## setup for auto-updating metrics

Create this file:

.github/workflows/metrics.yml

Then paste this:

```yml
name: Metrics

on:
  schedule: [{ cron: "0 */12 * * *" }]
  workflow_dispatch:
  push: { branches: ["main", "master"] }

jobs:
  github-metrics:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Generate Metrics
        uses: lowlighter/metrics@latest
        with:
          filename: github-metrics.svg
          token: ${{ secrets.METRICS_TOKEN }}

          user: YOUR_USERNAME
          template: classic
          base: header, activity, community, repositories, metadata

          config_timezone: Europe/Zurich

          plugin_languages: yes
          plugin_languages_limit: 8
          plugin_languages_sections: most-used
          plugin_languages_indepth: yes

          plugin_isocalendar: yes

          plugin_habits: yes
          plugin_habits_days: 14
          plugin_habits_facts: yes

          plugin_stars: yes

          plugin_followup: yes

          plugin_achievements: yes
          plugin_achievements_threshold: C
