# Use this file to configure the post-processing subsystem for the fault and benchmark types that you employed in
# your workload, together with the monitoring system that you used.

# List of fault types that are meaningful only when the system is not idling
busyFaults = ['cpufreq', 'pagefail', 'ioerr']

# List of fault types that only impact the core they are running on
localFaults = ['dial', 'ddot']

# Labels used in the post-processed CSV files
timeLabel = '#Time'
benchmarkLabel = '#Benchmark'
faultLabel = '#Fault'
mixedLabel = '#Mixed'
busyLabel = 'allocated'
derivLabel = '_der'

# Labels for metrics that are per-core and not aggregated, used in build_features
perCoreLabels = ['per_core_', '#']

# Whitelist of metrics to be considered in the filter_merge script
metricsWhitelist = ['#Time', 'Active', 'cpu_freq.0']

# Blacklist of metrics to be ignored in the build_features script
metricsBlacklist = [  # CONSTANT METRICS FROM PROCSTAT
                    '#Time', 'Time_usec', 'ProducerName', 'component_id', 'job_id', 'cores_up', 'cpu_enabled', 'irq',
                    'steal', 'guest', 'guest_nice', 'per_core_cpu_enabled0', 'per_core_cpu_enabled1', 'per_core_cpu_enabled2',
                    'per_core_cpu_enabled3', 'per_core_cpu_enabled4', 'per_core_cpu_enabled5', 'per_core_cpu_enabled6',
                    'per_core_cpu_enabled7', 'per_core_cpu_enabled8', 'per_core_cpu_enabled9', 'per_core_cpu_enabled10',
                    'per_core_cpu_enabled11', 'per_core_cpu_enabled12', 'per_core_cpu_enabled13', 'per_core_cpu_enabled14',
                    'per_core_cpu_enabled15', 'per_core_irq0', 'per_core_irq1', 'per_core_irq2', 'per_core_irq3', 'per_core_irq4',
                    'per_core_irq5', 'per_core_irq6', 'per_core_irq7', 'per_core_irq8', 'per_core_irq9', 'per_core_irq10',
                    'per_core_irq11', 'per_core_irq12', 'per_core_irq13', 'per_core_irq14', 'per_core_irq15', 'per_core_steal0',
                    'per_core_steal1', 'per_core_steal2', 'per_core_steal3', 'per_core_steal4', 'per_core_steal5', 'per_core_steal6',
                    'per_core_steal7', 'per_core_steal8', 'per_core_steal9', 'per_core_steal10', 'per_core_steal11', 'per_core_steal12',
                    'per_core_steal13', 'per_core_steal14', 'per_core_steal15', 'per_core_guest0', 'per_core_guest1', 'per_core_guest2',
                    'per_core_guest3', 'per_core_guest4', 'per_core_guest5', 'per_core_guest6', 'per_core_guest7', 'per_core_guest8',
                    'per_core_guest9', 'per_core_guest10', 'per_core_guest11', 'per_core_guest12', 'per_core_guest13', 'per_core_guest14',
                    'per_core_guest15', 'per_core_guest_nice0', 'per_core_guest_nice1', 'per_core_guest_nice2', 'per_core_guest_nice3',
                    'per_core_guest_nice4', 'per_core_guest_nice5', 'per_core_guest_nice6', 'per_core_guest_nice7', 'per_core_guest_nice8',
                    'per_core_guest_nice9', 'per_core_guest_nice10', 'per_core_guest_nice11', 'per_core_guest_nice12', 'per_core_guest_nice13',
                    'per_core_guest_nice14', 'per_core_guest_nice15',
                      # CONSTANT METRICS FROM MEMINFO
                    'MemTotal', 'Buffers', 'SwapCached', 'Unevictable', 'Mlocked', 'SwapTotal', 'SwapFree', 'NFS_Unstable',
                    'Bounce', 'WritebackTmp', 'CommitLimit', 'VmallocTotal', 'VmallocUsed', 'VmallocChunk', 'HardwareCorrupted',
                    'HugePages_Total', 'HugePages_Free', 'HugePages_Rsvd', 'HugePages_Surp', 'Hugepagesize', 'DirectMap4k', 'DirectMap2M', 'DirectMap1G',
                      # CONSTANT METRICS FROM VMSTAT
                    'nr_unevictable', 'nr_mlock', 'nr_unstable', 'nr_bounce', 'nr_vmscan_write', 'nr_vmscan_immediate_reclaim',
                    'nr_writeback_temp', 'nr_isolated_file', 'numa_miss', 'numa_foreign', 'numa_interleave', 'workingset_refault',
                    'workingset_activate', 'workingset_nodereclaim', 'nr_free_cma', 'pswpin', 'pswpout', 'pgalloc_dma', 'pgalloc_movable',
                    'pgdeactivate', 'pgrefill_dma', 'pgrefill_dma32', 'pgrefill_normal', 'pgrefill_movable', 'pgsteal_kswapd_dma', 'pgsteal_kswapd_dma32',
                    'pgsteal_kswapd_normal', 'pgsteal_kswapd_movable', 'pgsteal_direct_dma', 'pgsteal_direct_dma32', 'pgsteal_direct_normal', 'pgsteal_direct_movable',
                    'pgscan_kswapd_dma', 'pgscan_kswapd_dma32', 'pgscan_kswapd_normal', 'pgscan_kswapd_movable', 'pgscan_direct_dma', 'pgscan_direct_dma32',
                    'pgscan_direct_normal', 'pgscan_direct_movable', 'pgscan_direct_throttle', 'zone_reclaim_failed', 'pginodesteal', 'slabs_scanned', 'kswapd_inodesteal',
                    'kswapd_low_wmark_hit_quickly', 'kswapd_high_wmark_hit_quickly', 'pageoutrun', 'allocstall', 'pgrotated', 'drop_pagecache', 'drop_slab',
                    'compact_migrate_scanned', 'compact_free_scanned', 'compact_isolated', 'compact_stall', 'compact_fail', 'compact_success',
                    'htlb_buddy_alloc_success', 'htlb_buddy_alloc_fail', 'unevictable_pgs_culled', 'unevictable_pgs_scanned', 'unevictable_pgs_rescued',
                    'unevictable_pgs_mlocked', 'unevictable_pgs_munlocked', 'unevictable_pgs_cleared', 'unevictable_pgs_stranded',
                    'thp_fault_fallback', 'thp_collapse_alloc_failed', 'thp_zero_page_alloc', 'thp_zero_page_alloc_failed',
                      # CONSTANT METRICS FROM PERFEVENT
                    'per_core_PERF_COUNT_SW_CPU_MIGRATIONS15', 'per_core_PERF_COUNT_SW_CPU_MIGRATIONS14',
                    'per_core_PERF_COUNT_SW_CPU_MIGRATIONS13', 'per_core_PERF_COUNT_SW_CPU_MIGRATIONS12',
                    'per_core_PERF_COUNT_SW_CPU_MIGRATIONS11', 'per_core_PERF_COUNT_SW_CPU_MIGRATIONS10',
                    'per_core_PERF_COUNT_SW_CPU_MIGRATIONS9', 'per_core_PERF_COUNT_SW_CPU_MIGRATIONS8',
                    'per_core_PERF_COUNT_SW_CPU_MIGRATIONS7', 'per_core_PERF_COUNT_SW_CPU_MIGRATIONS6',
                    'per_core_PERF_COUNT_SW_CPU_MIGRATIONS5', 'per_core_PERF_COUNT_SW_CPU_MIGRATIONS4',
                    'per_core_PERF_COUNT_SW_CPU_MIGRATIONS3', 'per_core_PERF_COUNT_SW_CPU_MIGRATIONS2',
                    'per_core_PERF_COUNT_SW_CPU_MIGRATIONS1', 'per_core_PERF_COUNT_SW_CPU_MIGRATIONS0',
                    'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES15', 'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES14',
                    'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES13', 'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES12',
                    'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES11', 'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES10',
                    'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES9', 'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES8',
                    'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES7', 'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES6',
                    'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES5', 'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES4',
                    'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES3', 'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES2',
                    'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES1', 'per_core_PERF_COUNT_SW_CONTEXT_SWITCHES0',
                      # CONSTANT METRICS FROM PROCINTERRUPTS
                    'irq.0#0', 'irq.0#1', 'irq.0#2', 'irq.0#3', 'irq.0#4', 'irq.0#5', 'irq.0#6', 'irq.0#7', 'irq.0#8',
                    'irq.0#9', 'irq.0#10', 'irq.0#11', 'irq.0#12', 'irq.0#13', 'irq.0#14', 'irq.0#15', 'irq.8#0',
                    'irq.8#1', 'irq.8#2', 'irq.8#3', 'irq.8#4', 'irq.8#5', 'irq.8#6', 'irq.8#7', 'irq.8#8', 'irq.8#9',
                    'irq.8#10', 'irq.8#11', 'irq.8#12', 'irq.8#13', 'irq.8#14', 'irq.8#15', 'irq.17#0', 'irq.17#1',
                    'irq.17#2', 'irq.17#3', 'irq.17#4', 'irq.17#5', 'irq.17#6', 'irq.17#7', 'irq.17#8', 'irq.17#9',
                    'irq.17#10', 'irq.17#11', 'irq.17#12', 'irq.17#13', 'irq.17#14', 'irq.17#15', 'irq.18#0', 'irq.18#1',
                    'irq.18#2', 'irq.18#3', 'irq.18#4', 'irq.18#5', 'irq.18#6', 'irq.18#7', 'irq.18#8', 'irq.18#9', 'irq.18#10',
                    'irq.18#11', 'irq.18#12', 'irq.18#13', 'irq.18#14', 'irq.18#15', 'irq.25#0', 'irq.25#1', 'irq.25#2',
                    'irq.25#3', 'irq.25#4', 'irq.25#5', 'irq.25#6', 'irq.25#7', 'irq.25#8', 'irq.25#9', 'irq.25#10',
                    'irq.25#11', 'irq.25#12', 'irq.25#13', 'irq.25#14', 'irq.25#15', 'irq.26#0', 'irq.26#1', 'irq.26#2',
                    'irq.26#3', 'irq.26#4', 'irq.26#5', 'irq.26#6', 'irq.26#7', 'irq.26#8', 'irq.26#9', 'irq.26#10',
                    'irq.26#11', 'irq.26#12', 'irq.26#13', 'irq.26#14', 'irq.26#15', 'irq.27#0', 'irq.27#1', 'irq.27#2',
                    'irq.27#3', 'irq.27#4', 'irq.27#5', 'irq.27#6', 'irq.27#7', 'irq.27#8', 'irq.27#9', 'irq.27#10', 'irq.27#11',
                    'irq.27#12', 'irq.27#13', 'irq.27#14', 'irq.27#15', 'irq.28#0', 'irq.28#1', 'irq.28#2', 'irq.28#3',
                    'irq.28#4', 'irq.28#5', 'irq.28#6', 'irq.28#7', 'irq.28#8', 'irq.28#9', 'irq.28#10', 'irq.28#11',
                    'irq.28#12', 'irq.28#13', 'irq.28#14', 'irq.28#15', 'irq.29#0', 'irq.29#1', 'irq.29#2', 'irq.29#3',
                    'irq.29#4', 'irq.29#5', 'irq.29#6', 'irq.29#7', 'irq.29#8', 'irq.29#9', 'irq.29#10', 'irq.29#11',
                    'irq.29#12', 'irq.29#13', 'irq.29#14', 'irq.29#15', 'irq.47#0', 'irq.47#1', 'irq.47#2', 'irq.47#3',
                    'irq.47#4', 'irq.47#5', 'irq.47#6', 'irq.47#7', 'irq.47#8', 'irq.47#9', 'irq.47#10', 'irq.47#11',
                    'irq.47#12', 'irq.47#13', 'irq.47#14', 'irq.47#15', 'irq.49#0', 'irq.49#1', 'irq.49#2', 'irq.49#3',
                    'irq.49#4', 'irq.49#5', 'irq.49#6', 'irq.49#7', 'irq.49#8', 'irq.49#9', 'irq.49#10', 'irq.49#11',
                    'irq.49#12', 'irq.49#13', 'irq.49#14', 'irq.49#15', 'irq.66#0', 'irq.66#1', 'irq.66#2', 'irq.66#3',
                    'irq.66#4', 'irq.66#5', 'irq.66#6', 'irq.66#7', 'irq.66#8', 'irq.66#9', 'irq.66#10', 'irq.66#11',
                    'irq.66#12', 'irq.66#13', 'irq.66#14', 'irq.66#15', 'irq.84#0', 'irq.84#1', 'irq.84#2', 'irq.84#3',
                    'irq.84#4', 'irq.84#5', 'irq.84#6', 'irq.84#7', 'irq.84#8', 'irq.84#9', 'irq.84#10', 'irq.84#11',
                    'irq.84#12', 'irq.84#13', 'irq.84#14', 'irq.84#15', 'irq.86#0', 'irq.86#1', 'irq.86#2', 'irq.86#3',
                    'irq.86#4', 'irq.86#5', 'irq.86#6', 'irq.86#7', 'irq.86#8', 'irq.86#9', 'irq.86#10', 'irq.86#11',
                    'irq.86#12', 'irq.86#13', 'irq.86#14', 'irq.86#15', 'irq.88#0', 'irq.88#1', 'irq.88#2', 'irq.88#3',
                    'irq.88#4', 'irq.88#5', 'irq.88#6', 'irq.88#7', 'irq.88#8', 'irq.88#9', 'irq.88#10', 'irq.88#11',
                    'irq.88#12', 'irq.88#13', 'irq.88#14', 'irq.88#15', 'irq.89#0', 'irq.89#1', 'irq.89#2', 'irq.89#3',
                    'irq.89#4', 'irq.89#5', 'irq.89#6', 'irq.89#7', 'irq.89#8', 'irq.89#9', 'irq.89#10', 'irq.89#11',
                    'irq.89#12', 'irq.89#13', 'irq.89#14', 'irq.89#15', 'irq.90#0', 'irq.90#1', 'irq.90#2', 'irq.90#3',
                    'irq.90#4', 'irq.90#5', 'irq.90#6', 'irq.90#7', 'irq.90#8', 'irq.90#9', 'irq.90#10', 'irq.90#11',
                    'irq.90#12', 'irq.90#13', 'irq.90#14', 'irq.90#15', 'irq.91#0', 'irq.91#1', 'irq.91#2', 'irq.91#3',
                    'irq.91#4', 'irq.91#5', 'irq.91#6', 'irq.91#7', 'irq.91#8', 'irq.91#9', 'irq.91#10', 'irq.91#11',
                    'irq.91#12', 'irq.91#13', 'irq.91#14', 'irq.91#15', 'irq.92#0', 'irq.92#1', 'irq.92#2', 'irq.92#3',
                    'irq.92#4', 'irq.92#5', 'irq.92#6', 'irq.92#7', 'irq.92#8', 'irq.92#9', 'irq.92#10', 'irq.92#11',
                    'irq.92#12', 'irq.92#13', 'irq.92#14', 'irq.92#15', 'irq.93#0', 'irq.93#1', 'irq.93#2', 'irq.93#3',
                    'irq.93#4', 'irq.93#5', 'irq.93#6', 'irq.93#7', 'irq.93#8', 'irq.93#9', 'irq.93#10', 'irq.93#11',
                    'irq.93#12', 'irq.93#13', 'irq.93#14', 'irq.93#15', 'irq.94#0', 'irq.94#1', 'irq.94#2', 'irq.94#3',
                    'irq.94#4', 'irq.94#5', 'irq.94#6', 'irq.94#7', 'irq.94#8', 'irq.94#9', 'irq.94#10', 'irq.94#11',
                    'irq.94#12', 'irq.94#13', 'irq.94#14', 'irq.94#15', 'irq.96#0', 'irq.96#1', 'irq.96#2', 'irq.96#3',
                    'irq.96#4', 'irq.96#5', 'irq.96#6', 'irq.96#7', 'irq.96#8', 'irq.96#9', 'irq.96#10', 'irq.96#11',
                    'irq.96#12', 'irq.96#13', 'irq.96#14', 'irq.96#15', 'irq.98#0', 'irq.98#1', 'irq.98#2', 'irq.98#3',
                    'irq.98#4', 'irq.98#5', 'irq.98#6', 'irq.98#7', 'irq.98#8', 'irq.98#9', 'irq.98#10', 'irq.98#11',
                    'irq.98#12', 'irq.98#13', 'irq.98#14', 'irq.98#15', 'irq.99#0', 'irq.99#1', 'irq.99#2', 'irq.99#3',
                    'irq.99#4', 'irq.99#5', 'irq.99#6', 'irq.99#7', 'irq.99#8', 'irq.99#9', 'irq.99#10', 'irq.99#11',
                    'irq.99#12', 'irq.99#13', 'irq.99#14', 'irq.99#15', 'irq.100#0', 'irq.100#1', 'irq.100#2', 'irq.100#3',
                    'irq.100#4', 'irq.100#5', 'irq.100#6', 'irq.100#7', 'irq.100#8', 'irq.100#9', 'irq.100#10', 'irq.100#11',
                    'irq.100#12', 'irq.100#13', 'irq.100#14', 'irq.100#15', 'irq.101#0', 'irq.101#1', 'irq.101#2', 'irq.101#3',
                    'irq.101#4', 'irq.101#5', 'irq.101#6', 'irq.101#7', 'irq.101#8', 'irq.101#9', 'irq.101#10', 'irq.101#11',
                    'irq.101#12', 'irq.101#13', 'irq.101#14', 'irq.101#15', 'irq.102#0', 'irq.102#1', 'irq.102#2', 'irq.102#3',
                    'irq.102#4', 'irq.102#5', 'irq.102#6', 'irq.102#7', 'irq.102#8', 'irq.102#9', 'irq.102#10', 'irq.102#11',
                    'irq.102#12', 'irq.102#13', 'irq.102#14', 'irq.102#15', 'irq.103#0', 'irq.103#1', 'irq.103#2', 'irq.103#3',
                    'irq.103#4', 'irq.103#5', 'irq.103#6', 'irq.103#7', 'irq.103#8', 'irq.103#9', 'irq.103#10', 'irq.103#11',
                    'irq.103#12', 'irq.103#13', 'irq.103#14', 'irq.103#15', 'irq.104#0', 'irq.104#1', 'irq.104#2', 'irq.104#3',
                    'irq.104#4', 'irq.104#5', 'irq.104#6', 'irq.104#7', 'irq.104#8', 'irq.104#9', 'irq.104#10', 'irq.104#11',
                    'irq.104#12', 'irq.104#13', 'irq.104#14', 'irq.104#15', 'irq.SPU#0', 'irq.SPU#1', 'irq.SPU#2', 'irq.SPU#3',
                    'irq.SPU#4', 'irq.SPU#5', 'irq.SPU#6', 'irq.SPU#7', 'irq.SPU#8', 'irq.SPU#9', 'irq.SPU#10', 'irq.SPU#11',
                    'irq.SPU#12', 'irq.SPU#13', 'irq.SPU#14', 'irq.SPU#15', 'irq.RTR#0', 'irq.RTR#1', 'irq.RTR#2', 'irq.RTR#3',
                    'irq.RTR#4', 'irq.RTR#5', 'irq.RTR#6', 'irq.RTR#7', 'irq.RTR#8', 'irq.RTR#9', 'irq.RTR#10', 'irq.RTR#11',
                    'irq.RTR#12', 'irq.RTR#13', 'irq.RTR#14', 'irq.RTR#15', 'irq.TRM#0', 'irq.TRM#1', 'irq.TRM#2', 'irq.TRM#3',
                    'irq.TRM#4', 'irq.TRM#5', 'irq.TRM#6', 'irq.TRM#7', 'irq.TRM#8', 'irq.TRM#9', 'irq.TRM#10', 'irq.TRM#11',
                    'irq.TRM#12', 'irq.TRM#13', 'irq.TRM#14', 'irq.TRM#15', 'irq.THR#0', 'irq.THR#1', 'irq.THR#2', 'irq.THR#3',
                    'irq.THR#4', 'irq.THR#5', 'irq.THR#6', 'irq.THR#7', 'irq.THR#8', 'irq.THR#9', 'irq.THR#10', 'irq.THR#11',
                    'irq.THR#12', 'irq.THR#13', 'irq.THR#14', 'irq.THR#15', 'irq.MCE#0', 'irq.MCE#1', 'irq.MCE#2', 'irq.MCE#3',
                    'irq.MCE#4', 'irq.MCE#5', 'irq.MCE#6', 'irq.MCE#7', 'irq.MCE#8', 'irq.MCE#9', 'irq.MCE#10', 'irq.MCE#11',
                    'irq.MCE#12', 'irq.MCE#13', 'irq.MCE#14', 'irq.MCE#15'
                    ]

if __name__ == '__main__':
    print('There are currently %s entries in the metrics blacklist.' % len(metricsBlacklist))
    print('There are currently %s entries in the metrics whitelist.' % len(metricsWhitelist))
    exit(0)