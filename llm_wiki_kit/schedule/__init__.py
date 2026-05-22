"""``wiki schedule`` — CLI verb that fires an operation's ``period:`` declaration.

The package is an empty namespace at this commit: the public orchestration
surface (``install``, ``uninstall``, ``list_schedules``) lands in a later
PR per ``docs/specs/wiki-schedule/plan.md`` step 5. Until then the only
things importable from this package are the DSL helpers in
:mod:`llm_wiki_kit.schedule.dsl` and the internal ``_Emitter`` Protocol
in :mod:`llm_wiki_kit.schedule._emitter`, both reached by their full
dotted paths.
"""
