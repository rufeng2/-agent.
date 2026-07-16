<template>
  <section class="page-surface">
    <div class="page-heading">
      <div>
        <h1>建议审批</h1>
        <p>集中处理 Agent 生成的高风险和中风险运营建议，查看数据证据后再审批。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="load">刷新建议</el-button>
    </div>

    <div class="panel table-panel">
      <el-radio-group v-model="status" size="large" @change="load">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="pending">待审批</el-radio-button>
        <el-radio-button label="approved">已通过</el-radio-button>
        <el-radio-button label="rejected">已拒绝</el-radio-button>
      </el-radio-group>

      <el-table :data="items" stripe style="margin-top:14px">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="evidence-box">
              <h3>数据证据</h3>
              <el-table :data="row.evidence">
                <el-table-column prop="label" label="指标" />
                <el-table-column prop="value" label="当前值" />
                <el-table-column prop="baseline" label="基准" />
                <el-table-column prop="rule" label="触发规则" />
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="建议" min-width="180" />
        <el-table-column prop="risk_level" label="风险" width="100">
          <template #default="{ row }"><el-tag :type="row.risk_level === 'high' ? 'danger' : 'warning'">{{ row.risk_level }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="reason" label="触发原因" min-width="220" />
        <el-table-column prop="expected_impact" label="预期影响" min-width="180" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="version" label="版本" width="70" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" size="small" type="primary" @click="transition(row, 'approve')">通过</el-button>
            <el-button v-if="row.status === 'pending'" size="small" @click="transition(row, 'reject')">拒绝</el-button>
            <el-button size="small" text @click="showAudit(row.id)">审计</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-drawer v-model="auditVisible" title="审批审计" size="480px"><el-empty v-if="!audit.length" description="暂无审批记录"/><el-timeline><el-timeline-item v-for="item in audit" :key="item.created_at" :timestamp="item.created_at"><strong>{{ item.from_status }} → {{ item.to_status }}</strong><p>{{ item.operator }}：{{ item.comment || '无审批意见' }}</p></el-timeline-item></el-timeline></el-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { ecommerceAPI } from "@/api/client"

const status = ref("")
const loading = ref(false)
const items = ref<any[]>([])
const auditVisible=ref(false), audit=ref<any[]>([])

async function load() {
  loading.value = true
  try {
    items.value = (await ecommerceAPI.recommendations(status.value)).data.data
  } catch {
    ElMessage.error("建议列表加载失败")
  } finally {
    loading.value = false
  }
}

async function transition(row:any, action:"approve"|"reject") { const {value}=await ElMessageBox.prompt("请输入审批意见","审批确认",{inputPlaceholder:"说明通过或拒绝原因"}); if(action==="approve") await ecommerceAPI.approveRecommendation(row.id,row.version,value); else await ecommerceAPI.rejectRecommendation(row.id,row.version,value); ElMessage.success(action==="approve"?"建议已通过":"建议已拒绝"); await load() }
async function showAudit(id:string){const data=(await ecommerceAPI.recommendationDetail(id)).data.data;audit.value=data.approvals;auditVisible.value=true}

onMounted(load)
</script>

<style scoped>
.table-panel{padding:14px}.evidence-box{padding:8px 24px 18px}.evidence-box h3{margin:0 0 12px;font-size:15px}
</style>
