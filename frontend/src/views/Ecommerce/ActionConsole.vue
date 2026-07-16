<template>
  <section class="page-surface">
    <div class="page-heading"><div><h1>智能执行台</h1><p>Agent 生成变更方案，经人工审批后修改模拟商品与营销状态。</p></div><el-tag type="warning" effect="plain">Sandbox</el-tag></div>
    <div class="execution-flow"><div class="active"><span>1</span><strong>选择目标</strong></div><div :class="{active:proposal}"><span>2</span><strong>Agent 生成方案</strong></div><div :class="{active:recommendation?.status==='approved'}"><span>3</span><strong>人工审批</strong></div><div :class="{active:receipt}"><span>4</span><strong>工具执行并回写</strong></div></div>
    <div class="console-layout">
      <section class="panel control-panel">
        <h2>要让智能体做什么？</h2>
        <el-segmented v-model="actionType" :options="actions" block />
        <label>目标商品</label><el-select v-model="productId" filterable><el-option v-for="item in products" :key="item.product_id" :label="`${item.name} · ${item.listing_status==='listed'?'已上架':'已下架'} · ¥${item.price}`" :value="item.product_id" /></el-select>
        <template v-if="actionType==='price_update'"><label>新价格</label><el-input-number v-model="newPrice" :min="1" :precision="2" controls-position="right" /><small>单次调价幅度不能超过 20%，且不能低于成本。</small></template>
        <template v-if="actionType==='marketing_plan'"><label>营销目标</label><el-select v-model="goal"><el-option v-for="item in goals" :key="item" :value="item" /></el-select></template>
        <el-button type="primary" :loading="loading" @click="propose">让 Agent 生成执行方案</el-button>
      </section>
      <section class="panel proposal-panel">
        <el-empty v-if="!proposal" description="生成方案后，变更内容和风险会显示在这里" />
        <template v-else>
          <div class="proposal-title"><div><span>Agent 执行提案</span><h2>{{ proposal.title }}</h2></div><el-tag :type="proposal.risk_level==='high'?'danger':'warning'">{{ proposal.risk_level==='high'?'高风险':'中风险' }}</el-tag></div>
          <div class="proposal-grid"><div><span>执行原因</span><strong>{{ proposal.reason }}</strong></div><div><span>预期影响</span><strong>{{ proposal.expected_impact }}</strong></div></div>
          <el-descriptions v-if="actionType==='price_update'" :column="3" border><el-descriptions-item label="当前价格">¥{{ proposal.payload.old_price }}</el-descriptions-item><el-descriptions-item label="新价格">¥{{ proposal.payload.new_price }}</el-descriptions-item><el-descriptions-item label="调整幅度">{{ proposal.payload.change_pct }}%</el-descriptions-item></el-descriptions>
          <div v-if="proposal.payload.plan" class="plan-box"><strong>{{ proposal.payload.plan.theme }}</strong><div><el-tag v-for="item in proposal.payload.plan.strategy" :key="item">{{ item }}</el-tag></div></div>
          <div class="approval-block"><div><span>审批状态</span><strong>{{ recommendation.status==='approved'?'已批准':'等待批准' }}</strong></div><div class="buttons"><el-button v-if="recommendation.status==='pending'" type="primary" @click="approve">批准执行</el-button><el-button :disabled="recommendation.status!=='approved'" :loading="executing" @click="execute">执行变更</el-button></div></div>
        </template>
      </section>
    </div>
    <section v-if="receipt" class="panel receipt-panel"><div><span>执行完成</span><strong>{{ actionLabel(receipt.action_type) }}</strong><small>回执 {{ receipt.receipt_id }}</small></div><el-tag type="success">已写入模拟业务系统</el-tag></section>
    <div class="panel product-snapshot"><div class="snapshot-heading"><h2>当前商品状态</h2><el-button @click="loadProducts">刷新</el-button></div><el-table :data="products"><el-table-column prop="name" label="商品" /><el-table-column label="上下架"><template #default="{row}"><el-tag :type="row.listing_status==='listed'?'success':'info'">{{ row.listing_status==='listed'?'已上架':'已下架' }}</el-tag></template></el-table-column><el-table-column prop="price" label="当前售价"/><el-table-column prop="base_price" label="基础价格"/><el-table-column prop="catalog_version" label="变更版本"/></el-table></div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"
const actions=[{label:"商品上架",value:"product_publish"},{label:"商品下架",value:"product_unpublish"},{label:"价格调整",value:"price_update"},{label:"制定营销计划",value:"marketing_plan"}]
const goals=["大促增长","新品冷启动","清仓库存","会员复购"]
const actionType=ref("price_update"),productId=ref(""),newPrice=ref(0),goal=ref("大促增长"),products=ref<any[]>([]),proposal=ref<any>(null),recommendation=ref<any>(null),receipt=ref<any>(null),loading=ref(false),executing=ref(false)
async function loadProducts(){products.value=(await ecommerceAPI.products()).data.data;productId.value ||= products.value[0]?.product_id||"";const item=products.value.find((x:any)=>x.product_id===productId.value);if(item&&!newPrice.value)newPrice.value=item.price}
watch(productId,()=>{const item=products.value.find((x:any)=>x.product_id===productId.value);if(item)newPrice.value=item.price})
watch(actionType,()=>{proposal.value=null;recommendation.value=null;receipt.value=null})
async function propose(){loading.value=true;receipt.value=null;try{const parameters=actionType.value==="price_update"?{new_price:newPrice.value}:actionType.value==="marketing_plan"?{goal:goal.value}:{};const data=(await ecommerceAPI.createActionProposal(actionType.value,productId.value,parameters)).data.data;proposal.value=data.proposal;recommendation.value=data.recommendation}catch(error:any){ElMessage.error(error.response?.data?.detail||"执行方案生成失败")}finally{loading.value=false}}
async function approve(){recommendation.value=(await ecommerceAPI.approveRecommendation(recommendation.value.id,recommendation.value.version,"已检查变更范围，批准沙箱执行")).data.data;ElMessage.success("审批已通过")}
async function execute(){executing.value=true;try{receipt.value=(await ecommerceAPI.executeAction(recommendation.value.id)).data.data;await loadProducts();ElMessage.success("业务状态已更新")}catch(error:any){ElMessage.error(error.response?.data?.detail||"执行失败")}finally{executing.value=false}}
const actionLabel=(value:string)=>({product_publish:"商品上架",product_unpublish:"商品下架",price_update:"价格调整",marketing_plan:"营销计划创建"} as any)[value]||value
onMounted(loadProducts)
</script>

<style scoped>
.execution-flow{display:grid;grid-template-columns:repeat(4,1fr);margin-bottom:16px;border:1px solid var(--border);background:#fff}.execution-flow div{display:flex;align-items:center;gap:9px;padding:13px;color:var(--ink-muted);border-right:1px solid var(--border)}.execution-flow div:last-child{border-right:0}.execution-flow span{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:#eef2f6}.execution-flow .active{color:#1d4ed8}.execution-flow .active span{background:#2563eb;color:#fff}.console-layout{display:grid;grid-template-columns:360px minmax(0,1fr);gap:16px}.control-panel,.proposal-panel,.product-snapshot{padding:18px}.control-panel{display:grid;align-content:start;gap:12px}.control-panel h2,.snapshot-heading h2{margin:0;font-size:16px}.control-panel label{margin-top:5px;font-size:12px;font-weight:700}.control-panel small{color:var(--ink-muted);line-height:1.5}.proposal-title,.approval-block,.snapshot-heading,.receipt-panel{display:flex;align-items:center;justify-content:space-between;gap:16px}.proposal-title span,.proposal-grid span,.approval-block span,.receipt-panel span,.receipt-panel small{display:block;color:var(--ink-muted);font-size:12px}.proposal-title h2{margin:5px 0 0;font-size:18px}.proposal-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0}.proposal-grid>div{padding:13px;border:1px solid var(--border)}.proposal-grid strong{display:block;margin-top:5px;line-height:1.5}.plan-box{margin:16px 0;padding:14px;background:#f7f9f8}.plan-box .el-tag{margin:10px 8px 0 0}.approval-block{margin-top:18px;padding-top:16px;border-top:1px solid var(--border)}.buttons{display:flex;gap:8px}.receipt-panel{margin-top:16px;padding:16px;border-left:4px solid #16a34a}.receipt-panel strong{display:block;margin:4px 0}.product-snapshot{margin-top:16px}.snapshot-heading{margin-bottom:12px}@media(max-width:900px){.console-layout{grid-template-columns:1fr}.execution-flow{grid-template-columns:1fr 1fr}.proposal-grid{grid-template-columns:1fr}}@media(max-width:560px){.execution-flow{grid-template-columns:1fr}.proposal-title,.approval-block,.receipt-panel{align-items:flex-start;flex-direction:column}}
</style>
