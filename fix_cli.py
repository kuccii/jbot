with open(r'C:\Users\impat\OneDrive\Documents\GitHub\JBot\job-hunter\job_hunter\cli.py') as f:
    content = f.read()

# Find the cleanup function
old_start = content.index('def cleanup(')
# cleanup is the last function, so find the end of file
old_func = content[old_start:]

new_func = '''def cleanup(
    stale_days: int = typer.Option(30, help="Remove jobs older than N days"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    reclassify: bool = typer.Option(False, "--reclassify", help="Re-derive audience/gates/score for existing rows"),
):
    """Clean database: re-check eligibility, remove stale/duplicates."""
    _fix_console_encoding()

    cfg = load_config()

    if reclassify:
        from job_hunter import cleanup as _cleanup
        stats = _cleanup.reclassify(cfg.database, cfg)
        dupes = _cleanup.deduplicate(cfg.database)
        print("Reclassify complete:")
        print(f"  Re-derived/kept: {stats['kept']}")
        print(f"  Deleted (new):   {stats['removed']}")
        print(f"  Duplicates:      {dupes}")
        return

    from job_hunter.cleanup import full_cleanup

    if not yes:
        print("This will:")
        print("  1. Re-check eligibility on all jobs")
        print(f"  2. Remove jobs older than {stale_days} days with status 'new'")
        print("  3. Remove duplicates (keep newest)")
        if not typer.confirm("Continue?"):
            print("Cancelled.")
            return

    result = full_cleanup(cfg.database, stale_days)

    print(f"\\nCleanup complete:")
    print(f"  Eligibility removed: {result['eligibility_removed']}")
    print(f"  Stale removed:       {result['stale_removed']}")
    print(f"  Duplicates removed:  {result['dupes_removed']}")
    print(f"  Final total:         {result['final_total']}")
    print(f"  Final eligible:      {result['final_eligible']}")
'''

content = content[:old_start] + new_func
with open(r'C:\Users\impat\OneDrive\Documents\GitHub\JBot\job-hunter\job_hunter\cli.py', 'w') as f:
    f.write(content)
print('CLI updated with --reclassify option')