# Contributing

We'd love your help making `connect-python` better!

If you'd like to add new exported APIs, please [open an issue][open-issue]
describing your proposal - discussing API changes ahead of time makes
pull request review much smoother. In your issue, pull request, and any other
communications, please remember to treat your fellow contributors with
respect!

Note that for a contribution to be accepted, you must sign off on all commits
in order to affirm that they comply with the [Developer Certificate of Origin][dco].

## Setup

[Fork][fork], then clone the repository:

```
git clone git@github.com:your_github_username/connect-python.git
cd connect-python
git remote add upstream https://github.com/connectrpc/connect-python.git
git fetch upstream
```

Make sure that the tests and the linters pass.
Their usage is described [here](https://github.com/connectrpc/connect-python?tab=readme-ov-file#development).

## Making Changes

Start by creating a new branch for your changes:

```
git checkout main
git fetch upstream
git rebase upstream/main
git checkout -b cool_new_feature
```

Make your changes. When you're satisfied with your changes, push them to your fork.

```
git commit -a
git push origin cool_new_feature
```

Then use the GitHub UI to open a pull request.

At this point, you're waiting on us to review your changes. We _try_ to respond
to issues and pull requests within a few business days, and we may suggest some
improvements or alternatives. Once your changes are approved, one of the
project maintainers will merge them.

We're much more likely to approve your changes if you:

- Add tests for new functionality.
- Write a [good commit message][commit-message].
- Maintain backward compatibility.

[fork]: https://github.com/connectrpc/connect-python/fork
[open-issue]: https://github.com/connectrpc/connect-python/issues/new
[dco]: https://developercertificate.org
[commit-message]: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html
