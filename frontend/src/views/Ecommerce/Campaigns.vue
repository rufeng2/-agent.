<template>
  <section class="page-surface">
    <div class="page-heading">
      <div>
        <h1>活动策略</h1>
        <p>基于商品分层生成活动选品、优惠承接和投放建议。</p>
      </div>
      <div class="toolbar-row">
        <el-input v-model="goal" style="width: 220px" />
        <el-button type="primary" :loading="loading" @click="load">生成策略</el-button>
      </div>
    </div>

    <div v-if="plan" class="strategy-grid">
      <div v-if="effect" class="panel section-panel wide impact-summary">
        <h2>活动效果模拟测算</h2><p>增量 GMV {{ effect.incremental_gmv }} 元 · 优惠成本 {{ effect.discount_cost }} 元 · ROI {{ effect.roi }}</p><small>模拟测算，不代表真实业务承诺</small>
      </div>
      <div class="panel section-panel">
        <h2>{{ plan.theme }}</h2>
        <p class="muted">目标：{{ plan.goal }}</p>
        <el-tag v-for="item in plan.strategy" :key="item" style="margin:0 8px 8px 0">{{ item }}</el-tag>
      </div>

      <div class="panel section-panel">
        <h2>工具调用轨迹</h2>
        <el-timeline>
          <el-timeline-item v-for="step in plan.tool_trace" :key="step.tool_name" :timestamp="step.tool_name">{{ step.output_summary }}</el-timeline-item>
        </el-timeline>
      </div>

      <div class="panel section-panel wide">
        <h2>主推商品</h2>
        <el-table :data="plan.hero_products">
          <el-table-column prop="name" label="商品" />
          <el-table-column prop="segment" label="商品分层" />
          <el-table-column prop="gmv" label="GMV" />
          <el-table-column prop="gross_margin_rate" label="毛利率%" />
        </el-table>
      </div>

      <div class="panel section-panel wide">
        <h2>补充/清仓商品</h2>
        <el-table :data="plan.clearance_products">
          <el-table-column prop="name" label="商品" />
          <el-table-column prop="stock" label="库存" />
          <el-table-column prop="conversion_rate" label="转化率%" />
          <el-table-column prop="risk_tags" label="风险标签" />
        </el-table>
      </div>
    </div>
    <el-empty v-else description="生成活动策略后展示结果" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"

const goal = ref("大促增长")
const loading = ref(false)
const plan = ref<any>(null)
const effect = ref<any>(null)

async function load() {
  loading.value = true
  try {
    const [planResponse, effectResponse] = await Promise.all([ecommerceAPI.campaignPlan(goal.value), ecommerceAPI.campaignEffect()])
    plan.value = planResponse.data.data
    effect.value = effectResponse.data.data
  } catch {
    ElMessage.error("活动策略生成失败")
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.strategy-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.section-panel{padding:16px}.section-panel h2{margin:0 0 12px;font-size:16px}.wide{grid-column:1/-1}.muted,.impact-summary small{color:var(--ink-muted)}.impact-summary p{font-size:17px;font-weight:650}
@media(max-width:900px){.strategy-grid{grid-template-columns:1fr}}
</style>
