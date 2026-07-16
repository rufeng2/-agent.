<template>
  <section class="page-surface">
    <div class="page-heading">
      <div>
        <h1>商品分析</h1>
        <p>查看商品分层、ABC 分层、GMV 贡献、转化效率、毛利、库存周转和评价风险。</p>
      </div>
      <div class="toolbar-row">
        <el-tag size="large" type="info">模拟日期 {{ simulation?.current_date || "-" }}</el-tag>
        <el-button :loading="loading" @click="reset">重置模拟</el-button>
        <el-button type="primary" :loading="advancing" @click="advance">推进一天</el-button>
      </div>
    </div>

    <div v-if="simulation?.events?.length" class="event-band">
      <strong>今日经营事件</strong>
      <span v-for="event in simulation.events" :key="event">{{ event }}</span>
    </div>

    <div class="panel table-panel">
      <el-table :data="products" stripe>
        <el-table-column prop="name" label="商品" min-width="150" />
        <el-table-column prop="category" label="类目" width="110" />
        <el-table-column prop="segment" label="商品分层" width="110">
          <template #default="{ row }"><el-tag>{{ row.segment }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="abc_segment" label="ABC 分层" width="100">
          <template #default="{ row }"><el-tag type="success">{{ row.abc_segment }}</el-tag></template>
        </el-table-column>
        <el-table-column label="GMV" width="130"><template #default="{ row }"><span>{{ row.gmv }}</span><small :class="deltaClass(row.deltas.gmv)">{{ deltaText(row.deltas.gmv) }}</small></template></el-table-column>
        <el-table-column label="订单" width="105"><template #default="{ row }"><span>{{ row.orders }}</span><small :class="deltaClass(row.deltas.orders)">{{ deltaText(row.deltas.orders) }}</small></template></el-table-column>
        <el-table-column label="转化率" width="125"><template #default="{ row }"><span>{{ row.conversion_rate }}%</span><small :class="deltaClass(row.deltas.conversion_rate)">{{ deltaText(row.deltas.conversion_rate) }}</small></template></el-table-column>
        <el-table-column prop="gross_margin_rate" label="毛利率" width="110" />
        <el-table-column label="库存" width="110">
          <template #default="{ row }"><span>{{ row.stock }}/{{ row.safety_stock }}</span><small :class="deltaClass(row.deltas.stock)">{{ deltaText(row.deltas.stock) }}</small></template>
        </el-table-column>
        <el-table-column prop="inventory_turnover_days" label="周转天数" width="110" />
        <el-table-column label="广告 ROI" width="120"><template #default="{ row }"><span>{{ row.ad_roi }}</span><small :class="deltaClass(row.deltas.ad_roi)">{{ deltaText(row.deltas.ad_roi) }}</small></template></el-table-column>
        <el-table-column label="评分" width="100"><template #default="{ row }"><span>{{ row.average_rating }}</span><small :class="deltaClass(row.deltas.average_rating)">{{ deltaText(row.deltas.average_rating) }}</small></template></el-table-column>
        <el-table-column label="竞品价" width="120"><template #default="{ row }"><span>{{ row.competitor_price }}</span><small :class="deltaClass(row.deltas.competitor_price)">{{ deltaText(row.deltas.competitor_price) }}</small></template></el-table-column>
        <el-table-column prop="price_gap" label="价差" width="90" />
        <el-table-column prop="price_index" label="价格指数" width="100" />
        <el-table-column label="风险标签" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="tag in row.risk_tags" :key="tag" type="danger" style="margin-right:6px">{{ tag }}</el-tag>
            <span v-if="!row.risk_tags.length" class="muted">稳定</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { ecommerceAPI } from "@/api/client"

const loading = ref(false)
const products = ref<any[]>([])
const simulation = ref<any>(null)
const advancing = ref(false)

async function load() {
  loading.value = true
  try {
    const [productResponse, stateResponse] = await Promise.all([ecommerceAPI.products(), ecommerceAPI.simulationState()])
    products.value = productResponse.data.data
    simulation.value = stateResponse.data.data
  } catch {
    ElMessage.error("商品分析加载失败")
  } finally {
    loading.value = false
  }
}

function deltaText(value: number) {
  const numeric = Number(value || 0)
  if (!numeric) return ""
  return `${numeric > 0 ? "↑" : "↓"}${Math.abs(numeric)}`
}

function deltaClass(value: number) {
  return Number(value) > 0 ? "delta up" : Number(value) < 0 ? "delta down" : "delta"
}

async function advance() {
  if (!simulation.value) return
  advancing.value = true
  try {
    await ecommerceAPI.advanceSimulation(simulation.value.version)
    await load()
    ElMessage.success("已推进到下一模拟日")
  } catch (error: any) {
    if (error.response?.status === 409) await load()
    ElMessage.error(error.response?.status === 409 ? "状态已变化，已刷新最新数据" : "推进模拟失败")
  } finally {
    advancing.value = false
  }
}

async function reset() {
  if (!simulation.value || simulation.value.step === 0) return ElMessage.info("当前已是初始状态")
  await ElMessageBox.confirm("将清除当前模拟时间线并恢复初始商品数据。", "重置模拟", { type: "warning" })
  await ecommerceAPI.resetSimulation(simulation.value.version)
  await load()
  ElMessage.success("模拟已重置")
}

onMounted(load)
</script>

<style scoped>
.event-band{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;padding:12px 14px;color:#254034;background:#eef8f2;border:1px solid #cbe4d5;border-radius:6px}.event-band strong{margin-right:4px}.event-band span{padding:4px 8px;background:#fff;border:1px solid #d6e8dd;border-radius:4px;font-size:12px}.table-panel{padding:10px}.muted{color:var(--ink-muted);font-size:12px}.el-table span,.el-table small{display:block}.delta{min-height:16px;font-size:11px}.delta.up{color:var(--success)}.delta.down{color:var(--danger)}
</style>
