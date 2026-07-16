DEFAULT_EVALUATION_TARGETS = [
    {
        "name": "真实性",
        "description": "检查关键事实是否可靠，是否存在幻觉、旧信息当作新信息、预测当作事实等问题。",
        "weight": 50,
    },
    {
        "name": "完整性",
        "description": "检查输出是否覆盖任务关注点，是否遗漏关键公开信息。",
        "weight": 20,
    },
    {
        "name": "来源质量",
        "description": "检查来源是否可靠，是否能够支撑关键结论。",
        "weight": 10,
    },
    {
        "name": "稳定性",
        "description": "检查结果是否清晰一致，是否容易因为配置变化出现明显漂移。",
        "weight": 10,
    },
    {
        "name": "结构与表达",
        "description": "检查输出结构是否适合后续使用，表达是否清楚。",
        "weight": 5,
    },
    {
        "name": "成本效率",
        "description": "结合耗时、成本与输出质量判断性价比。",
        "weight": 5,
    },
]
