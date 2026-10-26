---
title: FAQ
description: Common questions about QStack.
sidebar:
  order: 5
banner:
  content: AI-generated (Claude Opus 5.5, <code>claude-opus-5-5</code>) and not yet human-verified.
---

## Is this an official QGIS project?

No. QStack is unofficial and not affiliated with QGIS.org. It repackages
plugins that are published on plugins.qgis.org; report problems with a
plugin itself to the plugin's own tracker.

## Can plugins be redistributed like this?

plugins.qgis.org requires plugins to be under a GPLv2-or-later-compatible
licence and to ship a `LICENSE` file. Those licences allow redistribution.
QStack packages the plugin unchanged, includes its `LICENSE`, and records the
SPDX licence in the package metadata.

## Why not just use QGIS's Plugin Manager?

The Plugin Manager installs the newest version into your user profile, with no
lock file and no Python dependencies. QStack puts plugins into the same
environment as QGIS, so the whole setup is declared in `pixi.toml`, resolved
together with the plugins' dependencies, and locked.

## The Plugin Manager offers an upgrade. Should I take it?

Not in a QStack workspace. An upgrade installs into your profile, and the
profile copy then shadows the packaged one (see
[Enabling plugins](/guides/enabling-plugins/)). Update the package instead
(`pixi update`).

## Can a published plugin version change?

Approved versions on plugins.qgis.org can't be edited, but they can be deleted
and re-uploaded with the same version number. QStack records the SHA-256 of
the ZIP it built from, so a changed upload is detected rather than silently
packaged.

## Why is my plugin's version different from the one on plugins.qgis.org?

Conda versions are stricter: `v4.23.1` becomes `4.23.1` and `2.0.0-beta1`
becomes `2.0.0beta1`. The upstream version is kept in the package's metadata.
See [Plugin version strings](/background/plugin-versions/).

## Does it work on Windows?

Not yet. QGIS's system plugin directory is under `Library\` on Windows, which
needs a separate package variant. It's planned.

## Are experimental plugin versions included?

No, only versions plugins.qgis.org marks as stable.
