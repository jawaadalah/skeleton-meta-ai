package com.jawaadalah.perangbintang

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.sin
import kotlin.random.Random

/** Game Ketuk Target: lingkaran konsentris berdenyut muncul acak, ketuk untuk poin. 30 detik. */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(GameView(this))
    }

    class GameView(context: Context) : View(context) {
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG)
        private var tx = 300f
        private var ty = 400f
        private val baseRadius = 92f
        private var skor = 0
        private var mulai = System.currentTimeMillis()
        private var selesai = false
        private var stars: List<Pair<Float, Float>> = emptyList()
        private val pops = mutableListOf<LongArray>()

        private fun pindah() {
            tx = Random.nextInt(130, maxOf(131, width - 130)).toFloat()
            ty = Random.nextInt(280, maxOf(281, height - 140)).toFloat()
        }

        private fun buatBintang() {
            val rnd = Random(7)
            stars = List(46) { rnd.nextInt(0, maxOf(1, width)).toFloat() to rnd.nextInt(0, maxOf(1, height)).toFloat() }
        }

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            if (stars.isEmpty() && width > 0) buatBintang()
            canvas.drawColor(Color.rgb(11, 16, 32))
            paint.color = Color.rgb(70, 90, 150)
            for ((sx, sy) in stars) canvas.drawCircle(sx, sy, 2.5f, paint)
            val sisa = 30 - (System.currentTimeMillis() - mulai) / 1000
            textPaint.color = Color.WHITE
            textPaint.textSize = 54f
            textPaint.isFakeBoldText = true
            if (sisa <= 0) {
                selesai = true
                textPaint.textSize = 62f
                canvas.drawText("Selesai! Skor akhir: $skor", 60f, height / 2f, textPaint)
                textPaint.textSize = 40f
                textPaint.isFakeBoldText = false
                canvas.drawText("Ketuk layar untuk main lagi", 60f, height / 2f + 76f, textPaint)
                return
            }
            canvas.drawText("Skor: $skor", 60f, 108f, textPaint)
            textPaint.textAlign = Paint.Align.RIGHT
            canvas.drawText("Waktu: $sisa", width - 60f, 108f, textPaint)
            textPaint.textAlign = Paint.Align.LEFT
            paint.color = Color.rgb(42, 51, 82)
            canvas.drawRect(60f, 140f, width - 60f, 156f, paint)
            paint.color = Color.rgb(34, 211, 238)
            canvas.drawRect(60f, 140f, 60f + (width - 120f) * sisa / 30f, 156f, paint)
            val pulse = (sin(System.currentTimeMillis() / 280.0) * 7).toFloat()
            val r = baseRadius + pulse
            paint.color = Color.argb(60, 255, 170, 40)
            canvas.drawCircle(tx, ty, r + 26f, paint)
            paint.color = Color.rgb(255, 170, 40)
            canvas.drawCircle(tx, ty, r, paint)
            paint.color = Color.WHITE
            canvas.drawCircle(tx, ty, r * 0.62f, paint)
            paint.color = Color.rgb(230, 60, 60)
            canvas.drawCircle(tx, ty, r * 0.3f, paint)
            val now = System.currentTimeMillis()
            val iter = pops.iterator()
            while (iter.hasNext()) {
                val p = iter.next()
                val age = (now - p[2]) / 700f
                if (age >= 1f) { iter.remove(); continue }
                textPaint.color = Color.argb((255 * (1f - age)).toInt(), 255, 210, 90)
                textPaint.textSize = 58f
                canvas.drawText("+1", p[0].toFloat() - 24f, p[1].toFloat() - age * 90f, textPaint)
                textPaint.color = Color.WHITE
            }
            postInvalidateDelayed(50)
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            if (event.action == MotionEvent.ACTION_DOWN) {
                if (selesai) {
                    skor = 0
                    mulai = System.currentTimeMillis()
                    selesai = false
                    pops.clear()
                    pindah()
                } else {
                    val dx = event.x - tx
                    val dy = event.y - ty
                    if (dx * dx + dy * dy <= baseRadius * baseRadius) {
                        skor++
                        pops.add(longArrayOf(tx.toLong(), ty.toLong(), System.currentTimeMillis()))
                        pindah()
                    }
                }
                invalidate()
            }
            return true
        }
    }
}
