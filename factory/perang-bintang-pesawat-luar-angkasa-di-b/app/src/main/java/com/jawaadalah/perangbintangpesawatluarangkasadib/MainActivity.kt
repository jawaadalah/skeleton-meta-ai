package com.jawaadalah.perangbintangpesawatluarangkasadib

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.os.SystemClock
import android.view.MotionEvent
import android.view.SurfaceHolder
import android.view.SurfaceView
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.max
import kotlin.math.min

class MainActivity : AppCompatActivity() {
    private lateinit var gameView: GameView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        gameView = GameView(this)
        setContentView(gameView)
    }

    override fun onPause() {
        super.onPause()
        gameView.pause()
    }

    override fun onResume() {
        super.onResume()
        gameView.resume()
    }

    // --------------------------------------------------------------
    // Inner classes for the game
    // --------------------------------------------------------------
    private class GameView(context: Context) : SurfaceView(context), SurfaceHolder.Callback, Runnable {
        private val threadLock = Object()
        private var thread: Thread? = null
        @Volatile private var running = false

        // Screen dimensions
        private var screenW = 0
        private var screenH = 0

        // Game objects
        private var shipX = 0f
        private var shipY = 0f
        private val shipWidth = 120f
        private val shipHeight = 40f

        private val asteroids = mutableListOf<Asteroid>()
        private val shots = mutableListOf<Shot>()

        // Paints
        private val paintShip = Paint().apply { color = Color.CYAN }
        private val paintAsteroid = Paint().apply { color = Color.DKGRAY }
        private val paintShot = Paint().apply { color = Color.YELLOW }
        private val paintText = Paint().apply {
            color = Color.WHITE
            textSize = 64f
            isAntiAlias = true
        }

        // Game state
        private var score = 0
        private var lives = 3
        private var lastAsteroidSpawn = 0L
        private var asteroidInterval = 1500L // ms
        private var lastShotTime = 0L
        private var shotInterval = 400L // ms
        private var gameOver = false

        init {
            holder.addCallback(this)
            isFocusable = true
        }

        // ----------------------------------------------------------
        // SurfaceHolder.Callback
        // ----------------------------------------------------------
        override fun surfaceCreated(holder: SurfaceHolder) {
            // start thread
            running = true
            thread = Thread(this)
            thread?.start()
        }

        override fun surfaceDestroyed(holder: SurfaceHolder) {
            // stop thread
            running = false
            synchronized(threadLock) {
                thread?.join()
                thread = null
            }
        }

        override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
            screenW = width
            screenH = height
            shipY = height - shipHeight * 2
            shipX = (width / 2).toFloat()
        }

        // ----------------------------------------------------------
        // Game loop
        // ----------------------------------------------------------
        override fun run() {
            var previousTime = SystemClock.uptimeMillis()
            while (running) {
                val now = SystemClock.uptimeMillis()
                val delta = now - previousTime
                if (delta >= 16) { // ~60 FPS
                    update()
                    drawGame()
                    previousTime = now
                } else {
                    try {
                        Thread.sleep(16 - delta)
                    } catch (e: InterruptedException) {
                    }
                }
            }
        }

        fun pause() {
            running = false
            synchronized(threadLock) {
                thread?.join()
                thread = null
            }
        }

        fun resume() {
            if (!running) {
                running = true
                thread = Thread(this)
                thread?.start()
            }
        }

        // ----------------------------------------------------------
        // Game logic
        // ----------------------------------------------------------
        private fun update() {
            if (gameOver) return

            val now = SystemClock.uptimeMillis()

            // Spawn asteroids
            if (now - lastAsteroidSpawn > asteroidInterval) {
                val size = 60f + (Math.random() * 40).toFloat()
                val x = (size / 2 + Math.random() * (screenW - size)).toFloat()
                asteroids.add(Asteroid(x, -size, size, 5f + (Math.random() * 5).toFloat()))
                lastAsteroidSpawn = now
            }

            // Move asteroids
            val iteratorA = asteroids.iterator()
            while (iteratorA.hasNext()) {
                val a = iteratorA.next()
                a.y += a.speed
                if (a.y - a.size > screenH) {
                    iteratorA.remove()
                    lives--
                    if (lives <= 0) {
                        gameOver = true
                    }
                }
            }

            // Fire shots
            if (now - lastShotTime > shotInterval) {
                shots.add(Shot(shipX, shipY - shipHeight / 2, 8f, 15f, 15f))
                lastShotTime = now
            }

            // Move shots
            val iteratorS = shots.iterator()
            while (iteratorS.hasNext()) {
                val s = iteratorS.next()
                s.y -= s.speed
                if (s.y + s.height < 0) {
                    iteratorS.remove()
                }
            }

            // Collision detection
            val shotIter = shots.iterator()
            while (shotIter.hasNext()) {
                val s = shotIter.next()
                val asteroidIter = asteroids.iterator()
                var hit = false
                while (asteroidIter.hasNext()) {
                    val a = asteroidIter.next()
                    if (RectF(
                            s.x - s.width / 2,
                            s.y - s.height,
                            s.x + s.width / 2,
                            s.y
                        ).intersect(
                            a.x - a.size / 2,
                            a.y - a.size / 2,
                            a.x + a.size / 2,
                            a.y + a.size / 2
                        )
                    ) {
                        // hit!
                        asteroidIter.remove()
                        hit = true
                        score += 10
                        break
                    }
                }
                if (hit) shotIter.remove()
            }
        }

        // ----------------------------------------------------------
        // Rendering
        // ----------------------------------------------------------
        private fun drawGame() {
            val canvas = holder.lockCanvas()
            if (canvas != null) {
                canvas.drawColor(Color.BLACK)

                // Draw ship
                val shipRect = RectF(
                    shipX - shipWidth / 2,
                    shipY - shipHeight / 2,
                    shipX + shipWidth / 2,
                    shipY + shipHeight / 2
                )
                canvas.drawRect(shipRect, paintShip)

                // Draw asteroids
                for (a in asteroids) {
                    canvas.drawCircle(a.x, a.y, a.size / 2, paintAsteroid)
                }

                // Draw shots
                for (s in shots) {
                    val shotRect = RectF(
                        s.x - s.width / 2,
                        s.y - s.height,
                        s.x + s.width / 2,
                        s.y
                    )
                    canvas.drawRect(shotRect, paintShot)
                }

                // Draw score and lives
                canvas.drawText("Score: $score", 20f, 70f, paintText)
                canvas.drawText("Lives: $lives", 20f, 140f, paintText)

                // Game over overlay
                if (gameOver) {
                    val msg = "Game Over! Tap to Restart"
                    val textWidth = paintText.measureText(msg)
                    canvas.drawText(
                        msg,
                        (screenW - textWidth) / 2,
                        (screenH / 2).toFloat(),
                        paintText
                    )
                }

                holder.unlockCanvasAndPost(canvas)
            }
        }

        // ----------------------------------------------------------
        // Touch handling
        // ----------------------------------------------------------
        override fun onTouchEvent(event: MotionEvent): Boolean {
            when (event.action) {
                MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                    if (gameOver) {
                        restartGame()
                    } else {
                        // Clamp ship within bounds
                        shipX = max(shipWidth / 2, min(event.x, screenW - shipWidth / 2))
                    }
                }
            }
            return true
        }

        private fun restartGame() {
            score = 0
            lives = 3
            asteroids.clear()
            shots.clear()
            lastAsteroidSpawn = SystemClock.uptimeMillis()
            lastShotTime = SystemClock.uptimeMillis()
            gameOver = false
        }

        // ----------------------------------------------------------
        // Data classes
        // ----------------------------------------------------------
        private data class Asteroid(
            var x: Float,
            var y: Float,
            var size: Float,
            var speed: Float
        )

        private data class Shot(
            var x: Float,
            var y: Float,
            var width: Float,
            var height: Float,
            var speed: Float
        )
    }
}