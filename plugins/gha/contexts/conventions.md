# GitHub Actions and Workflows Conventions

## Security

- Do not allow substitution of context variables directly into shell or script steps; save them into environment variables first, and use the environment variables in the scripts.

## Don't reimplement existing actions

- Before manually doing something that is likely common, like installing a tool or setting up authentication, search the internet to see if there is an existing reputable action that does it.
